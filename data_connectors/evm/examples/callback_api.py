# -*- coding: utf-8 -*-
from fastapi import FastAPI, Response

from app.pydantic_models import TransactionResultIn

app = FastAPI(title="EVM Connector Callback Example", version="1.0.0rc0")


@app.post("/callback/evm")
async def callback_evm(input_data: TransactionResultIn):
    """
    Callback from the EVM middleware with the result of a transaction verification.

    Args:
        input_data (TransactionResultIn): Transaction result data
    """
    # Log transaction result
    print(f"Transaction {input_data.transaction_hash} result: {input_data.result}")

    return Response(status_code=204)
