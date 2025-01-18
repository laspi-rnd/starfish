# -*- coding: utf-8 -*-
from os import getenv
from random import random
from time import sleep

import requests
from fastapi import BackgroundTasks, FastAPI, Response

from middleware.pydantic_models import TransactionResultIn, VerifyTransactionIn

TRUE_PROBABILITY = 0.75

app = FastAPI(title="EVM Connector Bypass", version="1.0.0rc0")


def call_middleware(transaction_hash: str):
    sleep_amount = 10 + random() * 5  # Sleep for 10-15 seconds
    sleep(sleep_amount)
    middleware_callback_url = getenv("MIDDLEWARE_CALLBACK_URL")
    requests.post(
        middleware_callback_url,
        data=TransactionResultIn(
            transaction_hash=transaction_hash, result=random() <= TRUE_PROBABILITY
        ).model_dump_json(),
    )


@app.post("/tx/verify/")
async def connector_bypass(
    input_data: VerifyTransactionIn, background_tasks: BackgroundTasks
):
    background_tasks.add_task(call_middleware, input_data.transaction_hash)
    return Response(status_code=204)
