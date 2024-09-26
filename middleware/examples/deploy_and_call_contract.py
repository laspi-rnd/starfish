# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path
from uuid import uuid4

from middleware.contracts import deploy_contract, invoke, query

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # Get compiled LISTRACK contract
    repo_root = Path(__file__).parent.parent.parent
    compiled_contract = (
        repo_root
        / "listrack"
        / "artifacts"
        / "contracts"
        / "LISTRACK_ETH.sol"
        / "LISTRACK_ETH.json"
    )
    if not compiled_contract.exists():
        raise FileNotFoundError("Compiled LISTRACK contract not found")
    api_name = f"listrack-{uuid4().hex[:8]}"
    api_name = loop.run_until_complete(
        deploy_contract(compiled_contract, api_name=api_name)
    )
    print(f"Contract deployed at API name {api_name}")
    # Some mock data here
    result = loop.run_until_complete(
        invoke(
            api_name,
            method="setTrade",
            parameters={
                "_mikeDrexAddress": "0xeCBC60138b48904adC8c4ed1e53F865dC608F886",
                "_aliceEthAddress": "0xeCBC60138b48904adC8c4ed1e53F865dC608F886",
                "_mikeEthAddress": "0xeCBC60138b48904adC8c4ed1e53F865dC608F886",
                "_drexAmount": 1,
                "_ethAmount": 1,
                "_nonce": 1,
            },
        )
    )
    print(f"Trade set: {result}")
    result2 = loop.run_until_complete(
        query(
            api_name,
            method="getTradeId",
            parameters={
                "_aliceDrexAddress": "0xeCBC60138b48904adC8c4ed1e53F865dC608F886",
                "_mikeDrexAddress": "0xeCBC60138b48904adC8c4ed1e53F865dC608F886",
                "_drexAmount": 1,
                "_ethAmount": 1,
                "_nonce": 1,
            },
        )
    )
    print(f"Trade ID: {result2}")
