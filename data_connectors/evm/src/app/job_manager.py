# -*- coding: utf-8 -*-
from redis import Redis as SyncRedis
from redis.asyncio import Redis as AsyncRedis

from app.config import settings
from app.enums import JobStatus
from app.pydantic_models import JobVerifyTransactionResult


class JobManager:
    def __init__(self):
        self._async_redis = AsyncRedis.from_url(settings.redis_url)
        self._sync_redis = SyncRedis.from_url(settings.redis_url)

    def _get_job_key(self, job_id: str):
        return f"jobs:{job_id}"

    def _get_job_alive_key(self, job_id: str):
        return f"{self._get_job_key(job_id)}:alive"

    async def init_job(self, job_id: str):
        job_key = self._get_job_key(job_id)
        job_alive_key = self._get_job_alive_key(job_id)
        await self._async_redis.hset(job_key, mapping={"status": JobStatus.PENDING})
        await self._async_redis.setex(job_alive_key, settings.job_timeout, 1)

    async def get_job_information(
        self, job_id: str
    ) -> JobVerifyTransactionResult | None:
        job_key = self._get_job_key(job_id)
        job_data = await self._async_redis.hgetall(job_key)
        if not job_data:
            return None
        result = job_data.get(b"result")
        return JobVerifyTransactionResult(
            job_id=job_id,
            status=JobStatus(job_data.get(b"status").decode()),
            result=bool(result) if result else None,
        )

    def set_job_status_and_result(
        self, job_id: str, status: JobStatus, result: bool | None
    ):
        job_key = self._get_job_key(job_id)
        self._sync_redis.hset(job_key, mapping={"status": status})
        if result is not None:
            self._sync_redis.hset(job_key, mapping={"result": int(result)})

    def is_job_alive(self, job_id: str) -> bool:
        return self._sync_redis.exists(self._get_job_alive_key(job_id))


job_manager = JobManager()
