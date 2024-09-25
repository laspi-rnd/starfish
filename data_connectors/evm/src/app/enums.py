# -*- coding: utf-8 -*-
from enum import Enum


class JobStatus(str, Enum):
    """
    Job status enumeration.
    """

    PENDING = "pending"
    FAILED = "failed"
    COMPLETED = "completed"
