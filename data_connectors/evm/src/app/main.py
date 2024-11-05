# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Response

from app.job_manager import job_manager
from app.pydantic_models import VerifyTransactionIn
from app.tasks import verify_transaction_data

app = FastAPI(title="Starfish EVM Connector", version="1.0.0rc0")


@app.post(
    "/tx/verify/",
    responses={
        204: {"description": "Transaction verification job started"},
        409: {"description": "Transaction verification job already exists"},
        404: {"description": "Transaction not found"},
    },
    response_model=None,
)
async def start_verification_job(input_data: VerifyTransactionIn):
    # Check if job already exists
    job_id = input_data.transaction_hash
    if await job_manager.transaction_is_pending_confirmation(job_id):
        raise HTTPException(
            status_code=409, detail="Transaction verification job already exists"
        )

    # Send task to Celery
    verify_transaction_data.delay(
        input_data.from_address,
        input_data.to_address,
        input_data.amount,
        input_data.transaction_hash,
    )

    return Response(status_code=204)
