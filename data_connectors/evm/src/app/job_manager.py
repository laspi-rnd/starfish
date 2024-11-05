# -*- coding: utf-8 -*-
from typing import List

from loguru import logger
from redis import Redis as SyncRedis
from redis.asyncio import Redis as AsyncRedis
from redis.lock import Lock

from app.config import settings


class JobManager:
    def __init__(self):
        self._async_redis = AsyncRedis.from_url(settings.redis_url)
        self._sync_redis = SyncRedis.from_url(settings.redis_url)
        self._validate_transactions_lock: Lock = self._sync_redis.lock(
            "validate_transactions_lock", timeout=settings.validate_transactions_timeout
        )

    def _get_job_key(self, job_id: str):
        return f"jobs:{job_id}"

    def _get_job_alive_key(self, job_id: str):
        return f"{self._get_job_key(job_id)}:alive"

    def _get_latest_confirmed_block_key(self):
        return "second_verification:latest_confirmed_block"

    @property
    def validate_transactions_lock(self):
        return self._validate_transactions_lock

    def get_latest_confirmed_block(self) -> int:
        key = self._get_latest_confirmed_block_key()
        return int(self._sync_redis.get(key) or 0)

    def set_latest_confirmed_block(self, block_number: int):
        key = self._get_latest_confirmed_block_key()
        self._sync_redis.set(key, block_number)

    def send_to_second_verification(self, tx_hash: str, block_number: int):
        # Add the transaction to the sorted set by block number
        self._sync_redis.zadd("transactions_by_block", {tx_hash: block_number})
        # Add the transaction to the specific block's set
        self._sync_redis.sadd(f"block:{block_number}:transactions", tx_hash)

    def count_transactions_to_confirm(self, min_block: int, max_block: int) -> int:
        return self._sync_redis.zcount(
            "transactions_by_block", min=min_block, max=max_block
        )

    def get_transactions_to_confirm_by_block_number(
        self, block_number: int
    ) -> List[str]:
        return [
            tx_hash.decode()
            for tx_hash in self._sync_redis.smembers(
                f"block:{block_number}:transactions"
            )
        ]

    def get_transactions_to_confirm_by_block_range(
        self, min_block: int, max_block: int
    ) -> List[str]:
        return [
            tx_hash.decode()
            for tx_hash in self._sync_redis.zrangebyscore(
                "transactions_by_block", min=min_block, max=max_block
            )
        ]

    async def transaction_is_pending_confirmation(self, tx_hash: str) -> bool:
        return (
            await self._async_redis.zscore("transactions_by_block", tx_hash) is not None
        )

    def remove_transaction(self, tx_hash: str, block_number: int = None):
        if not block_number:
            block_number = int(
                self._sync_redis.zscore("transactions_by_block", tx_hash)
            )
        self._sync_redis.zrem("transactions_by_block", tx_hash)
        self._sync_redis.srem(f"block:{block_number}:transactions", tx_hash)

    def set_transaction_result(self, tx_hash: str, result: bool):
        from app.tasks import send_transaction_result_to_middleware

        logger.info(f"Transaction {tx_hash} verified: {result}")
        send_transaction_result_to_middleware.delay(tx_hash, result)


job_manager = JobManager()
