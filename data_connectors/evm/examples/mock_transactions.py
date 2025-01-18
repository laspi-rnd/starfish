# -*- coding: utf-8 -*-
import asyncio
from random import choice, uniform
from time import time

from loguru import logger
from web3 import AsyncHTTPProvider, AsyncWeb3

# Get Web3 instance
JSON_RPC_URL = "https://rpc-evm-sidechain.xrpl.org/"
web3 = AsyncWeb3(AsyncHTTPProvider(JSON_RPC_URL))

# WARNING: These ACCOUNTS, and their private keys, are publicly known.
# Any funds sent to them on Mainnet or any other live network WILL BE LOST.
ACCOUNTS = [
    {
        "address": web3.to_checksum_address(
            "0xfe3b557e8fb62b89f4916b721be55ceb828dbd73"
        ),
        "private_key": "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63",
    },
    {
        "address": web3.to_checksum_address(
            "0x627306090abaB3A6e1400e9345bC60c78a8BEf57"
        ),
        "private_key": "0xc87509a1c067bbde78beb793e6fa76530b6382a4c0241e5e4a9ec0a0f44dc0d3",
    },
    {
        "address": web3.to_checksum_address(
            "0xf17f52151EbEF6C7334FAD080c5704D77216b732"
        ),
        "private_key": "0xae6ae8e5ccbfb04590405997ee2d52d2b330726137b875053c36d94e974d162f",
    },
]
TX_RATE = 15  # transactions per second

# Track nonces for each account
nonce_tracker = {account["address"]: None for account in ACCOUNTS}


async def send_random_transaction():
    # Choose random sender and receiver
    sender = choice(ACCOUNTS)
    receiver = choice(ACCOUNTS)

    # Ensure sender and receiver are not the same
    while receiver == sender:
        receiver = choice(ACCOUNTS)

    # Generate a random transaction amount
    amount = uniform(0.001, 0.01)  # e.g., in ether

    # Convert amount to Wei (replace with appropriate denomination for your network)
    amount_in_wei = web3.to_wei(amount, "ether")

    # Ensure nonce is unique for each transaction
    if nonce_tracker[sender["address"]] is None:
        nonce_tracker[sender["address"]] = await web3.eth.get_transaction_count(
            sender["address"]
        )

    # Create the transaction dictionary
    transaction = {
        "to": receiver["address"],
        "value": amount_in_wei,
        "gas": 21000,
        "gasPrice": await web3.eth.gas_price,
        "nonce": nonce_tracker[sender["address"]],
    }

    # Update nonce for next transaction
    nonce_tracker[sender["address"]] += 1

    # Sign the transaction
    signed_txn = web3.eth.account.sign_transaction(transaction, sender["private_key"])

    # Send the transaction
    try:
        tx_hash = await web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        logger.info(
            f"Transaction sent: {tx_hash.hex()} from {sender['address']} to {receiver['address']} with {amount} ether"
        )
    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        # Reset nonce if transaction fails
        nonce_tracker[sender["address"]] = None


async def transaction_scheduler():
    while True:
        try:
            start = time()
            tasks = [send_random_transaction() for _ in range(TX_RATE)]
            await asyncio.gather(*tasks)
            await asyncio.sleep(max(0, 1 - time() + start))
        except KeyboardInterrupt:
            logger.info("Exiting...")


async def main():
    await transaction_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
