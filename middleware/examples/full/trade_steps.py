# -*- coding: utf-8 -*-
import asyncio

from middleware.config import settings
from middleware.contracts import query, invoke
from middleware.utils import get_my_org


def break_point(title: str):
    c = input(title)
    if c == "q":
        exit()


async def main():
    # A few parameters we'll need later
    alice_drex_address = await get_my_org()
    mike_drex_address = alice_drex_address
    alice_eth_address = alice_drex_address
    mike_eth_address = alice_drex_address
    drex_amount = 1
    eth_amount = 1
    nonce = 1

    # 1. Alice sets the trade details in the Listrack contract.
    break_point("Press Enter to set trade details in the Listrack contract")
    await invoke(
        api_name=settings.listrack_contract_api_name,
        method="setTrade",
        namespace=settings.namespace,
        parameters={
            "_mikeDrexAddress": mike_drex_address,
            "_aliceEthAddress": alice_eth_address,
            "_mikeEthAddress": mike_eth_address,
            "_drexAmount": drex_amount,
            "_ethAmount": eth_amount,
            "_nonce": nonce,
        },
    )
    print("Trade details set")
    print()

    # 2. Get trade ID
    break_point("Press Enter to get trade ID")
    trade_id = await query(
        api_name=settings.listrack_contract_api_name,
        method="getTradeId",
        namespace=settings.namespace,
        parameters={
            "_aliceDrexAddress": alice_drex_address,
            "_mikeDrexAddress": mike_drex_address,
            "_drexAmount": drex_amount,
            "_ethAmount": eth_amount,
            "_nonce": nonce,
        },
    )["output"]
    print(f"Trade ID: {trade_id}")
    print()

    # 3. Mike agrees to the trade.
    break_point("Press Enter for Mike to agree to the trade")
    await invoke(
        api_name=settings.listrack_contract_api_name,
        method="agreeTrade",
        namespace=settings.namespace,
        parameters={"tradeId": trade_id},
    )
    print("Mike agreed to the trade")
    print()

    # 4. Alice submits her ETH transaction hash (dummy value).
    break_point("Press Enter for Alice to submit her ETH transaction hash")
    await invoke(
        api_name=settings.listrack_contract_api_name,
        method="submitTransactionHash",
        namespace=settings.namespace,
        parameters={"tradeId": trade_id, "_ethTransactionHash": "0x1234"},
    )
    print("Alice submitted her ETH transaction hash")
    print()

    # 5. Loop showing trade status
    while True:
        break_point("Press Enter to check trade status")
        trade_status = await query(
            api_name=settings.listrack_contract_api_name,
            method="getTradeStatus",
            namespace=settings.namespace,
            parameters={"tradeId": trade_id},
        )["output"]
        print(f"Trade status: {trade_status}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
