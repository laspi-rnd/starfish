# -*- coding: utf-8 -*-
from pydantic import BaseModel

from middleware.enums import MessageType
from middleware.types import JSONSerializable


class EventCheckTransaction(BaseModel):
    aliceEthAddress: str
    mikeEthAddress: str
    ethAmount: int
    ethTransactionHash: str


class FireFlySmartContract(BaseModel):
    blockchain_address: str
    interface_id: str
    api_name: str


class Message(BaseModel):
    from_org: str
    data: JSONSerializable
    type: MessageType
