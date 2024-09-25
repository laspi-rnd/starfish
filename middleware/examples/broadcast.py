# -*- coding: utf-8 -*-
import asyncio

from middleware.messaging import broadcast

if __name__ == "__main__":
    asyncio.run(broadcast("this is a test"))
