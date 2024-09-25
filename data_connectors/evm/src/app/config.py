# -*- coding: utf-8 -*-
import sys

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    block_confirmations: int = Field(
        description="Number of blocks to wait for finality"
    )
    celery_broker_url: str = Field(description="URL of the Celery broker")
    celery_job_retry_delay: int = Field(
        description="Delay in seconds before retrying a failed job", default=18
    )
    celery_job_retry_max_retries: int = Field(
        description="Maximum number of retries for a failed job", default=20
    )
    eth_node_url: str = Field(description="URL of the Ethereum node")
    redis_url: str = Field(description="URL of the Redis server")
    job_timeout: int = Field(
        description="Timeout in seconds for a job to complete", default=3600
    )


settings = Settings()
sys.modules[__name__].__dict__.update(settings.model_dump())
