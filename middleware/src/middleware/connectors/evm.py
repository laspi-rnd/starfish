# -*- coding: utf-8 -*-
import aiohttp

from middleware.config import settings
from middleware.pydantic_models import VerifyTransactionIn


async def start_verification_job(input_data: VerifyTransactionIn) -> None:
    base_url = settings.connector_evm_api_base_url.rstrip("/")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/tx/verify/",
            data=input_data.model_dump_json(),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
