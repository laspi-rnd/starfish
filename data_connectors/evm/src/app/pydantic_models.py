# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional

from app.enums import JobStatus


class JobVerifyTransactionResult(BaseModel):
    job_id: str
    status: JobStatus
    result: Optional[bool]


class VerifyTransactionIn(BaseModel):
    from_address: str
    to_address: str
    amount: int
    transaction_hash: str
