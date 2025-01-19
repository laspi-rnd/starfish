# -*- coding: utf-8 -*-
import asyncio
import hashlib
import json
import os
from pathlib import Path
from random import randint

from web3 import Web3


LISTRACK_ARTIFACT_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "listrack"
    / "artifacts"
    / "contracts"
    / "LISTRACK_ETH.sol"
)
LISTRACK_CONTRACT_ADDRESS = Web3.to_checksum_address(
    "0x66fdddcad3a0aa74271e41189cf60c1619619148"
)  # TODO (developer): update this with the deployed contract address
with open(LISTRACK_ARTIFACT_PATH / "LISTRACK_ETH.json") as f:
    LISTRACK_CONTRACT_ABI = json.load(f)["abi"]
NETWORK_NODE_URI = "http://localhost:44950"

# WARNING: These accounts, and their private keys, are publicly known.
# Any funds sent to them on Mainnet or any other live network WILL BE LOST.

# Alice is Account #15
ALICE_DREX_ADDRESS = "0xcd3B766CCDd6AE721141F452C550Ca635964ce71"
ALICE_PRIVATE_KEY = "0x8166f546bab6da521a8369cab06c5d2b9e46670292d85c875ee9ec20e84ffb61"

# Mike is Account #16
MIKE_DREX_ADDRESS = "0x2546BcD3c84621e976D8185a91A922aE77ECEc30"
MIKE_PRIVATE_KEY = "0xea6c44ac03bff858b476bba40716402b03e41b8e97e276d1baec7c37d42484a0"


w3 = Web3(Web3.HTTPProvider(NETWORK_NODE_URI))

if not w3.is_connected():
    print("Could not connect to network node")
    exit()

LISTRACK_CONTRACT = w3.eth.contract(
    address=LISTRACK_CONTRACT_ADDRESS, abi=LISTRACK_CONTRACT_ABI
)


def break_point(title: str):
    c = input(title)
    if c == "q":
        exit()


async def main():
    # A few parameters we'll need later
    drex_amount = 1
    eth_amount = 1
    nonce = randint(0, 2**256 - 1)

    # 1. Alice sets the trade details in the Listrack contract.
    break_point("Press Enter to set trade details in the Listrack contract")
    trade_id = LISTRACK_CONTRACT.functions.setTrade(
        MIKE_DREX_ADDRESS,
        ALICE_DREX_ADDRESS,  # This is Alice's ETH address, but we're using the same for simplicity
        MIKE_DREX_ADDRESS,  # This is Mike's ETH address, but we're using the same for simplicity
        drex_amount,
        eth_amount,
        nonce,
    ).call(
        {
            "from": ALICE_DREX_ADDRESS,
        }
    )
    tx = LISTRACK_CONTRACT.functions.setTrade(
        MIKE_DREX_ADDRESS,
        ALICE_DREX_ADDRESS,  # This is Alice's ETH address, but we're using the same for simplicity
        MIKE_DREX_ADDRESS,  # This is Mike's ETH address, but we're using the same for simplicity
        drex_amount,
        eth_amount,
        nonce,
    ).build_transaction(
        {
            "from": ALICE_DREX_ADDRESS,
            "nonce": w3.eth.get_transaction_count(ALICE_DREX_ADDRESS),
            "gas": 3000000,
            "gasPrice": w3.to_wei("10", "gwei"),
        }
    )
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=ALICE_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Trade details set. Trade ID: {trade_id}")
    print()

    # 2. Mike agrees to the trade.
    break_point("Press Enter for Mike to agree to the trade")
    trade_data = LISTRACK_CONTRACT.functions.trades(trade_id).call()
    transaction = LISTRACK_CONTRACT.functions.agreeTrade(trade_id).build_transaction(
        {
            "from": MIKE_DREX_ADDRESS,
            "value": trade_data[4],
            "gas": 300000,
            "gasPrice": w3.to_wei("10", "gwei"),
            "nonce": w3.eth.get_transaction_count(MIKE_DREX_ADDRESS),
        }
    )
    signed_tx = w3.eth.account.sign_transaction(
        transaction, private_key=MIKE_PRIVATE_KEY
    )
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Mike agreed to the trade")
    print()

    # 3. Alice submits her ETH transaction hash (dummy value).
    break_point("Press Enter for Alice to submit her ETH transaction hash")
    eth_transaction_hash = "0x" + hashlib.sha3_256(os.urandom(32)).hexdigest()
    tx = LISTRACK_CONTRACT.functions.submitTransactionHash(
        trade_id, eth_transaction_hash
    ).build_transaction(
        {
            "from": ALICE_DREX_ADDRESS,
            "nonce": w3.eth.get_transaction_count(ALICE_DREX_ADDRESS),
            "gas": 200000,
            "gasPrice": w3.to_wei("20", "gwei"),
        }
    )
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=ALICE_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Alice submitted her ETH transaction hash")
    print()

    # 4. Loop showing trade status
    while True:
        break_point("Press Enter to check trade status")
        trade_status = LISTRACK_CONTRACT.functions.trades(trade_id).call()
        print(f"Trade status: {trade_status}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
