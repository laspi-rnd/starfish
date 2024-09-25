# -*- coding: utf-8 -*-
import asyncio

from middleware.messaging import listen_messages
from middleware.types import JSONSerializable


async def on_message(message: JSONSerializable) -> None:
    print(f"Received message: {message}")


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
