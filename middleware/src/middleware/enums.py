# -*- coding: utf-8 -*-
from enum import Enum


class CheckTransactionStateEnum(int, Enum):
    LEADER_ELECTION = 1
    CHECKING_TRANSACTION = 2
    VOTING = 3
    COMMITTING = 4
    FINISHED_SUCCESS = 5
    FINISHED_FAILED = 6


class FireFlyUrlTypeEnum(str, Enum):
    REST = "rest"
    WS = "ws"


class MessageType(str, Enum):
    BROADCAST = "broadcast"
    PRIVATE = "private"
