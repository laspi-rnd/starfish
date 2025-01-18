# -*- coding: utf-8 -*-
import sys
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    connector_evm_api_base_url: str = Field(description="EVM connector API base URL")
    firefly_api_host: str = Field(description="Firefly API host")
    firefly_api_port: int = Field(description="Firefly API port")
    firefly_api_scheme: str = Field(description="Firefly API scheme")
    listrack_contract_api_name: str = Field(description="Listrack contract API name")
    listrack_contract_json_path: Optional[str] = Field(
        description="Listrack contract JSON path"
    )
    listrack_event_check_transaction: Optional[str] = Field(
        description="Listrack event check transaction",
        default="CheckTransaction",
    )
    message_forwarding_max_hops: int = Field(
        description="Message forwarding max hops",
        default=5,
    )
    namespace: Optional[str] = Field(description="Namespace", default="default")
    ntp_server: str = Field(description="NTP server", default="a.st1.ntp.br")
    redis_url: str = Field(description="URL of the Redis server")
    state_manager_loop_interval: int = Field(
        description="State manager loop interval in seconds", default=1
    )


settings = Settings()
sys.modules[__name__].__dict__.update(settings.model_dump())
