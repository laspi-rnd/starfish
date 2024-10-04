# -*- coding: utf-8 -*-
"""
Starfish Core.

This is the entry point for the Starfish Core. It spins up the Core and keeps it running.
For setting up the Core, see `src/middleware/config.py` file for configuration options. All of those
options can be set through environment variables.
"""

# To do list:
# - Implement handlers for both events and messages at the state manager
# - Implement some sort of mechanism to sync the state between peers

import asyncio
from pathlib import Path

from loguru import logger

from middleware.config import settings
from middleware.contracts import deploy_contract, get_contract, listen_events
from middleware.enums import StarfishMessageType
from middleware.listrack import get_contract_owner
from middleware.messaging import broadcast, listen_messages
from middleware.pydantic_models import (
    EventCheckTransaction,
    Message,
    StarfishMessageAskForEthereumAddress,
    StarfishMessageEthereumAddress,
)
from middleware.state_manager import state_manager
from middleware.types import JSONSerializable
from middleware.utils import get_my_ethereum_address, parse_message


async def callback_check_transaction_event(event_message: JSONSerializable) -> None:
    # Parse event
    event = EventCheckTransaction(**event_message["blockchainEvent"]["output"])
    logger.info(f"Received CheckTransaction event: {event}")

    # Call state manager to handle the event
    await state_manager.handle_event(event)


async def callback_listen_messages(message: JSONSerializable) -> None:
    # Get message data
    message_data: Message = parse_message(message)
    logger.info(f"Received message with data: {message_data}")

    # Call state manager to handle the message
    await state_manager.handle_message(message_data)


async def main():
    logger.info("Starting Starfish Core...")
    my_ethereum_address = await get_my_ethereum_address()
    logger.info(f"My Ethereum address: {my_ethereum_address}")

    # Check whether the LISTRACK smart contract is already deployed. If not, deploy it.
    listrack_contract = await get_contract(
        api_name=settings.listrack_contract_api_name, namespace=settings.namespace
    )
    if not listrack_contract:
        logger.info("LISTRACK contract not found. Will deploy it now...")
        if not settings.listrack_contract_json_path:
            raise ValueError("Listrack contract JSON path is not provided")
        listrack_contract_path = Path(settings.listrack_contract_json_path)
        if not listrack_contract_path.exists():
            raise FileNotFoundError(
                f'Listrack contract JSON file not found at "{listrack_contract_path}"'
            )
        logger.info(f"Deploying LISTRACK contract from {listrack_contract_path}")
        listrack_contract = await deploy_contract(
            contract_json=listrack_contract_path,
            api_name=settings.listrack_contract_api_name,
            namespace=settings.namespace,
        )
    logger.info(f"LISTRACK contract: {listrack_contract}")

    # Check if I'm the contract owner
    contract_owner = await get_contract_owner(namespace=settings.namespace)
    logger.info(f"Contract owner: {contract_owner}")
    # If I am the contract owner, I'll ask for the Ethereum address of all peers in the network
    if my_ethereum_address == contract_owner:
        logger.info(
            "I'm the contract owner. Asking for Ethereum addresses of all peers..."
        )
        message = StarfishMessageAskForEthereumAddress()
        await broadcast(
            data={
                "type": StarfishMessageType.ASK_FOR_ETHEREUM_ADDRESS,
                **message.model_dump(),
            },
            namespace=settings.namespace,
        )
    # If I'm not, I'll send a message to all peers asking to be added to the whitelist
    else:
        # TODO: Check whether I'm already added to the whitelist before sending this message
        logger.info(
            "I'm not the contract owner. Sending my address to all peers so I can be added to the whitelist..."
        )
        message = StarfishMessageEthereumAddress(address=my_ethereum_address)
        await broadcast(
            data={
                "type": StarfishMessageType.ETHEREUM_ADDRESS,
                **message.model_dump(),
            },
            namespace=settings.namespace,
        )

    # Start listening to LISTRACK's "CheckTransaction" events
    listen_listrack_task = await listen_events(
        contract=listrack_contract,
        event_name=settings.listrack_event_check_transaction,
        on_message=callback_check_transaction_event,
        namespace=settings.namespace,
    )
    logger.info(
        f"Listening to LISTRACK's {settings.listrack_event_check_transaction} events..."
    )

    # Start listening to other peer's messages
    listen_messages_task = await listen_messages(
        on_message=callback_listen_messages, namespace=settings.namespace
    )
    logger.info("Listening to peer's messages...")

    # Loop in order to keep the Core running
    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.warning("Got KeyboardInterrupt. Stopping the Core...")
            break

    # Stop listening to LISTRACK's "CheckTransaction" events
    listen_listrack_task.cancel()

    # Stop listening to other peer's messages
    listen_messages_task.cancel()

    logger.info("Core stopped. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
