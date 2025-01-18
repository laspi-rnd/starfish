# -*- coding: utf-8 -*-
from fastapi import FastAPI, Response
from loguru import logger

from middleware.pydantic_models import TransactionResultIn
from middleware.state_manager import state_manager

app = FastAPI(title="EVM Connector Callback API", version="1.0.0rc0")


@app.post("/callback/evm")
async def callback_evm(input_data: TransactionResultIn):
    """
    Callback from the EVM middleware with the result of a transaction verification.

    Args:
        input_data (TransactionResultIn): Transaction result data
    """
    # Log transaction result
    logger.info(
        f"Transaction {input_data.transaction_hash} result: {input_data.result}"
    )
    await state_manager.set_transaction_vote(
        input_data.transaction_hash, input_data.result
    )

    return Response(status_code=204)
