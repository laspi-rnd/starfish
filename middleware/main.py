# -*- coding: utf-8 -*-
"""
Starfish Core.

This is the entry point for the Starfish Core. It spins up the Core and keeps it running.
For setting up the Core, see `src/middleware/config.py` file for configuration options. All of those
options can be set through environment variables.
"""

# To do list:
# - Add peer discovery and adding those peers to LISTRACK's middleware whitelist
# - Add checking if belongs / asking to be added by other peers to the whitelist
# - Implement handlers for both events and messages at the state manager
# - Implement some sort of mechanism to sync the state between peers

import asyncio
from pathlib import Path

from loguru import logger

from middleware.config import settings
from middleware.contracts import deploy_contract, get_contract, listen_events
from middleware.messaging import listen_messages
from middleware.pydantic_models import EventCheckTransaction
from middleware.state_manager import state_manager
from middleware.types import JSONSerializable


async def callback_check_transaction_event(event_message: JSONSerializable) -> None:
    # Parse event
    event = EventCheckTransaction(**event_message["blockchainEvent"]["output"])
    logger.info(f"Received CheckTransaction event: {event}")

    # Call state manager to handle the event
    await state_manager.handle_event(event)


async def callback_listen_messages(message: JSONSerializable) -> None:
    # Get message data
    message_data: JSONSerializable = message["data"][0]["value"]
    logger.info(f"Received message with data: {message_data}")

    # Call state manager to handle the message
    await state_manager.handle_message(message_data)


async def main():
    logger.info("Starting Starfish Core...")

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
