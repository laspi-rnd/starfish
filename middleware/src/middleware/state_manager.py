# -*- coding: utf-8 -*-
from pydantic import BaseModel
from redis.asyncio import Redis

from middleware.config import settings
from middleware.enums import CheckTransactionStateEnum, StarfishMessageType
from middleware.listrack import add_peer_to_whitelist, get_contract_owner
from middleware.messaging import send_private_message
from middleware.pydantic_models import (
    EventCheckTransaction,
    Message,
    StarfishMessageAskForEthereumAddress,
    StarfishMessageEthereumAddress,
)
from middleware.utils import get_my_ethereum_address


MESSAGE_TO_MODEL = {
    StarfishMessageType.ASK_FOR_ETHEREUM_ADDRESS: StarfishMessageAskForEthereumAddress,
    StarfishMessageType.ETHEREUM_ADDRESS: StarfishMessageEthereumAddress,
}


class StateManager:
    def __init__(self):
        self._redis = Redis.from_url(settings.redis_url)

    def _parse_message_content(self, message: Message) -> BaseModel:
        starfish_message_type = message.data.get("type")
        if not starfish_message_type:
            raise ValueError("Message does not have a type")
        model = MESSAGE_TO_MODEL.get(starfish_message_type)
        if not model:
            raise ValueError(
                f"Unsupported Starfish message type: {starfish_message_type}"
            )
        return model(**{k: v for k, v in message.data.items() if k != "type"})

    async def get_peer_address(self, org: str) -> str:
        address = await self._redis.get(f"peer:{org}:address")
        return address.decode() if address else ""

    async def set_peer_address(self, org: str, address: str) -> None:
        await self._redis.set(f"peer:{org}:address", address)

    async def get_state(
        self, transaction_hash: str
    ) -> CheckTransactionStateEnum | None:
        state = await self._redis.get(transaction_hash)
        return CheckTransactionStateEnum(int(state)) if state else None

    async def set_state(
        self, transaction_hash: str, state: CheckTransactionStateEnum
    ) -> None:
        await self._redis.set(transaction_hash, state.value, ex=settings.state_ttl)

    async def handle_event(self, event: EventCheckTransaction) -> None:
        # TODO: Implement this function
        pass

    async def handle_message(self, message: Message) -> None:
        # Parse message content
        content = self._parse_message_content(message)

        # If a peer is asking for our Ethereum address, send it
        if isinstance(content, StarfishMessageAskForEthereumAddress):
            my_ethereum_address = await get_my_ethereum_address()
            message_to_send = StarfishMessageEthereumAddress(
                address=my_ethereum_address
            )
            await send_private_message(
                data={
                    "type": StarfishMessageType.ETHEREUM_ADDRESS,
                    **message_to_send.model_dump(),
                },
                to_org=message.from_org,
                namespace=settings.namespace,
            )
            return

        # If a peer is sending their Ethereum address, store it and, if we are the contract owner,
        # add the peer to LISTRACK's whitelist
        if isinstance(content, StarfishMessageEthereumAddress):
            # Store peer's Ethereum address
            await self.set_peer_address(message.from_org, content.address)
            # If we are the contract owner, add the peer to LISTRACK's whitelist
            my_ethereum_address = await get_my_ethereum_address()
            contract_owner_address = await get_contract_owner(
                namespace=settings.namespace
            )
            if my_ethereum_address == contract_owner_address:
                await add_peer_to_whitelist(content.address)
            return

        raise ValueError(f"Unsupported message type: {message.data.get('type')}")


state_manager = StateManager()
