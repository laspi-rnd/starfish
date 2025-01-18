# -*- coding: utf-8 -*-
from enum import Enum


class FireFlyUrlTypeEnum(str, Enum):
    REST = "rest"
    WS = "ws"


class MessageType(str, Enum):
    BROADCAST = "broadcast"
    PRIVATE = "private"


class StarfishMessageType(str, Enum):
    ASK_FOR_ETHEREUM_ADDRESS = "ask_for_ethereum_address"
    ETHEREUM_ADDRESS = "ethereum_address"
    PEER_SENT_OWN_VOTE = "peer_sent_own_vote"
    PEER_SENT_COMPUTED_RESULT = "peer_sent_computed_result"
