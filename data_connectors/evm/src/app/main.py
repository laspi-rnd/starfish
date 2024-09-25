# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException

from app.enums import JobStatus
from app.job_manager import job_manager
from app.pydantic_models import JobVerifyTransactionResult, VerifyTransactionIn
from app.tasks import verify_transaction

app = FastAPI(title="Starfish EVM Connector", version="1.0.0rc0")


@app.post(
    "/tx/verify/",
    responses={
        409: {"detail": "Transaction verification job already exists"},
        404: {"detail": "Transaction not found"},
    },
    response_model=JobVerifyTransactionResult,
)
async def start_verification_job(input_data: VerifyTransactionIn):
    # Check if job already exists
    job_id = input_data.transaction_hash
    data = await job_manager.get_job_information(job_id)
    if data is not None and data.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=409, detail="Transaction verification job already exists"
        )

    # Initialize job
    await job_manager.init_job(job_id=job_id)

    # Send task to Celery
    verify_transaction.delay(
        job_id,
        input_data.from_address,
        input_data.to_address,
        input_data.amount,
        input_data.transaction_hash,
    )

    # Return job information
    data = await job_manager.get_job_information(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return data


@app.get(
    "/tx/{transaction_hash}",
    responses={404: {"detail": "Transaction not found"}},
    response_model=JobVerifyTransactionResult,
)
async def check_transaction_status(transaction_hash: str) -> JobVerifyTransactionResult:
    # Return job information
    data = await job_manager.get_job_information(transaction_hash)
    if data is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return data
