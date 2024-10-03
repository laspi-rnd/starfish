# -*- coding: utf-8 -*-
import sys
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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
    listrack_function_settle_trade: Optional[str] = Field(
        description="Listrack function settle trade", default="settleTrade"
    )
    namespace: Optional[str] = Field(description="Namespace", default="default")
    state_ttl: int = Field(description="State time to live in seconds")


settings = Settings()
sys.modules[__name__].__dict__.update(settings.model_dump())
