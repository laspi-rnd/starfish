# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path
from uuid import uuid4

from middleware.contracts import deploy_contract, invoke, listen_events, query
from middleware.types import JSONSerializable


async def on_message(message: JSONSerializable) -> None:
    print(f"Event data: {message["blockchainEvent"]["output"]}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Get compiled SimpleStorage contract
    repo_root = Path(__file__).parent.parent.parent
    compiled_contract = (
        repo_root
        / "listrack"
        / "artifacts"
        / "contracts"
        / "SimpleStorage.sol"
        / "SimpleStorage.json"
    )
    if not compiled_contract.exists():
        raise FileNotFoundError("Compiled SimpleStorage contract not found")

    # Deploy the contract
    api_name = f"simplestorage-{uuid4().hex[:8]}"
    deployed_contract = loop.run_until_complete(
        deploy_contract(compiled_contract, api_name=api_name)
    )
    api_name = deployed_contract.api_name
    print(f"Contract deployed: {deployed_contract}")

    # Start listening for events
    listen_task = loop.run_until_complete(
        listen_events(
            contract=deployed_contract, event_name="Changed", on_message=on_message
        )
    )

    # Set with some mock data
    result = loop.run_until_complete(
        invoke(
            api_name,
            method="set",
            parameters={
                "newValue": 1,
            },
        )
    )
    print(f"Called `set`: {result}")

    # Get the value
    result2 = loop.run_until_complete(
        query(
            api_name,
            method="get",
        )
    )
    print(f"Called `get`: {result2}")

    # Wait for a while before exiting
    loop.run_until_complete(asyncio.sleep(10))

    # Stop listening for events
    listen_task.cancel()
