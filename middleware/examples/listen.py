# -*- coding: utf-8 -*-
import asyncio

from middleware.messaging import listen_messages
from middleware.types import JSONSerializable
from middleware.utils import parse_message


async def on_message(message: JSONSerializable) -> None:
    print(f"Received message: {parse_message(message)}")


async def main() -> None:
    ws_task = await listen_messages(on_message)

    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            break

    ws_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
