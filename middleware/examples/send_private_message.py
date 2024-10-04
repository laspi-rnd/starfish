# -*- coding: utf-8 -*-
import asyncio

from middleware.messaging import send_private_message

if __name__ == "__main__":
    asyncio.run(send_private_message("this is a test", to_org="org_f5f198"))
