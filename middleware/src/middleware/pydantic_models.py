# -*- coding: utf-8 -*-
from pydantic import BaseModel


class FireFlySmartContract(BaseModel):
    blockchain_address: str
    interface_id: str
    api_name: str
