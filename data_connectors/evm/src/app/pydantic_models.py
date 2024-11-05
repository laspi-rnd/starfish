# -*- coding: utf-8 -*-
from pydantic import BaseModel


class TransactionResultIn(BaseModel):
    transaction_hash: str
    result: bool


class VerifyTransactionIn(BaseModel):
    from_address: str
    to_address: str
    amount: int
    transaction_hash: str
