# -*- coding: utf-8 -*-
from redis.asyncio import Redis

from middleware.config import settings
from middleware.enums import CheckTransactionStateEnum
from middleware.pydantic_models import EventCheckTransaction
from middleware.types import JSONSerializable


class StateManager:
    def __init__(self):
        self._redis = Redis.from_url(settings.redis_url)

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

    async def handle_message(self, message: JSONSerializable) -> None:
        # TODO: Implement this function
        pass


state_manager = StateManager()
