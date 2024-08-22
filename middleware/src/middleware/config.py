# -*- coding: utf-8 -*-
import sys

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    state_ttl: int = Field(description="State time to live in seconds")


settings = Settings()
sys.modules[__name__].__dict__.update(settings.model_dump())
