# -*- coding: utf-8 -*-
from typing import Dict, Optional

from pydantic import BaseModel

from middleware.enums import MessageType
from middleware.types import JSONSerializable


class CheckTransactionState(BaseModel):
    start_time: int

    coordinator_weights: Dict[str, float] = {}
    peer_votes: Dict[str, bool] = {}
    coordinator: Optional[str] = None
    result: Optional[bool] = None
    results: Dict[str, bool] = {}

    aliceEthAddress: str
    mikeEthAddress: str
    ethAmount: int
    ethTransactionHash: str


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


class StarfishMessageAskForEthereumAddress(BaseModel):
    pass


class StarfishMessageEthereumAddress(BaseModel):
    address: str


class StarfishMessagePeerSentOwnVote(BaseModel):
    tx_hash: str
    coordinator_weight: float
    vote: bool


class StarfishMessagePeerSentComputedResult(BaseModel):
    tx_hash: str
    result: bool
    coordinator: str
    hops: int
    originally_from: str


class TransactionResultIn(BaseModel):
    transaction_hash: str
    result: bool


class VerifyTransactionIn(BaseModel):
    from_address: str
    to_address: str
    amount: int
    transaction_hash: str
