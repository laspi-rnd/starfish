# -*- coding: utf-8 -*-
from pydantic import BaseModel


class EventCheckTransaction(BaseModel):
    aliceEthAddress: str
    mikeEthAddress: str
    ethAmount: int
    ethTransactionHash: str


class FireFlySmartContract(BaseModel):
    blockchain_address: str
    interface_id: str
    api_name: str
