# -*- coding: utf-8 -*-
import sys

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    celery_broker_url: str = Field(description="URL of the Celery broker")
    eth_node_url: str = Field(description="URL of the Ethereum node")
    middleware_base_url: str = Field(description="Base URL of the middleware")
    redis_url: str = Field(description="URL of the Redis server")
    validate_transactions_timeout: int = Field(
        description="Timeout in seconds for the transaction validation lock", default=10
    )
    verify_block_data_interval: int = Field(
        description="Interval in seconds to verify block data", default=12
    )


settings = Settings()
sys.modules[__name__].__dict__.update(settings.model_dump())
