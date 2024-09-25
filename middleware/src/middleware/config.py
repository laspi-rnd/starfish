# -*- coding: utf-8 -*-
import sys

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    firefly_api_host: str = Field(description="Firefly API host")
    firefly_api_port: int = Field(description="Firefly API port")
    firefly_api_scheme: str = Field(description="Firefly API scheme")
    state_ttl: int = Field(description="State time to live in seconds")


settings = Settings()
sys.modules[__name__].__dict__.update(settings.model_dump())
