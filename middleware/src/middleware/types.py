# -*- coding: utf-8 -*-
from typing import Union, List, Dict

JSONSerializable = Union[
    None, bool, int, float, str, List["JSONSerializable"], Dict[str, "JSONSerializable"]
]
