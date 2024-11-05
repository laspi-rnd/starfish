# -*- coding: utf-8 -*-
from celery import Celery, Task
from loguru import logger
from web3 import Web3
import requests

from app.config import settings
from app.job_manager import job_manager
from app.pydantic_models import TransactionResultIn

celery = Celery("tasks", broker=settings.celery_broker_url)
w3 = Web3(Web3.HTTPProvider(settings.eth_node_url))


celery.conf.beat_schedule = {
    "verify-block-data": {
        "task": "app.tasks.verify_block_data",
        "schedule": settings.verify_block_data_interval,
    }
}


@celery.task(bind=True)
def verify_transaction_data(
    self: Task,
    from_eth_address: str,
    to_eth_address: str,
    amount: int,
    transaction_hash: str,
):
    """
    Verify if the transaction data matches the expected values.

    Args:
        from_eth_address (str): From Ethereum address
        to_eth_address (str): To Ethereum address
        amount (int): Amount to transfer
        transaction_hash (str): Transaction hash
    """
    try:
        # Get transaction by hash
        tx = w3.eth.get_transaction(transaction_hash)

        # Verify sender
        if tx["from"].lower() != from_eth_address.lower():
            logger.error(
                f"Transaction {transaction_hash} was sent by {tx['from']}, expected {from_eth_address}"
            )
            job_manager.set_transaction_result(transaction_hash, False)
            return

        # Verify receiver
        if tx["to"].lower() != to_eth_address.lower():
            logger.error(
                f"Transaction {transaction_hash} was sent to {tx['to']}, expected {to_eth_address}"
            )
            job_manager.set_transaction_result(transaction_hash, False)
            return

        # Verify amount
        if tx["value"] != amount:
            logger.error(
                f"Transaction {transaction_hash} was sent with {tx['value']} wei, expected {amount} wei"
            )
            job_manager.set_transaction_result(transaction_hash, False)
            return

        # Transaction data matches, we'll now send it to later verification
        logger.info(
            f"Transaction {transaction_hash} data matches. Sending to second stage."
        )
        job_manager.send_to_second_verification(transaction_hash, tx["blockNumber"])

    except Exception as exc:
        logger.error(f"Error verifying transaction {transaction_hash}: {exc}")
        job_manager.set_transaction_result(transaction_hash, False)


@celery.task(bind=True)
def verify_block_data(self: Task):
    """
    Get data from latest block that's finalized and check if we can confirm any transaction that's
    pending from our cache.
    """
    # TODO: Review if we should refactor this as an async task as it is mostly I/O bound
    if job_manager.validate_transactions_lock.locked():
        logger.warning("Transaction validation is already in progress. Skipping...")
        return
    with job_manager.validate_transactions_lock:
        # Get latest finalized block receipts
        latest_finalized_block_receipts = w3.eth.get_block_receipts("finalized")

        # Infer the block number from one of the receipts
        block_number = latest_finalized_block_receipts[0]["blockNumber"]
        logger.info(f"Latest finalized block: {block_number}")

        # Get our latest confirmed block
        latest_confirmed_block = job_manager.get_latest_confirmed_block()
        logger.info(f"Latest confirmed block: {latest_confirmed_block}")

        # Transactions that are from blocks lower than the latest confirmed block must be confirmed
        # - Get the number of transactions whose block number is between the genesis block and the
        #   latest confirmed block
        n_old_transactions = job_manager.count_transactions_to_confirm(
            0, latest_confirmed_block
        )
        logger.info(f"Old transactions to confirm: {n_old_transactions}")
        # - If there are transactions to confirm, we get them and simply confirm them
        if n_old_transactions > 0:
            old_transactions = job_manager.get_transactions_to_confirm_by_block_range(
                0, latest_confirmed_block
            )
            for tx_hash in old_transactions:
                job_manager.set_transaction_result(tx_hash, True)
                job_manager.remove_transaction(tx_hash)

        # Transactions that are from blocks between the latest confirmed block and the latest finalized
        # block must be verified individually
        # - Get the number of transactions whose block number is between the latest confirmed block and
        #   the latest finalized block
        n_new_transactions = job_manager.count_transactions_to_confirm(
            latest_confirmed_block + 1, block_number
        )
        logger.info(f"New transactions to confirm: {n_new_transactions}")
        # - If there are transactions to confirm, we iterate over block numbers and get receipts
        if n_new_transactions > 0:
            for block_number in range(latest_confirmed_block + 1, block_number + 1):
                # Get transactions to confirm for this block
                new_transactions = (
                    job_manager.get_transactions_to_confirm_by_block_number(
                        block_number
                    )
                )
                # If there are no transactions, we continue to the next block
                if not new_transactions:
                    logger.info(f"No transactions to confirm for block {block_number}")
                    continue
                logger.info(
                    f"Verifying {len(new_transactions)} transactions for block {block_number}"
                )

                # Get block receipts
                block_receipts = w3.eth.get_block_receipts(block_number)
                block_receipts_hashes = {
                    receipt["transactionHash"].to_0x_hex(): receipt["status"]
                    for receipt in block_receipts
                }

                # For each transaction, check if it belongs to the block and if it was successful
                for tx_hash in new_transactions:
                    # If the transaction is not found in the block, we must get its own receipt and
                    # check if it was successful
                    if tx_hash not in block_receipts_hashes:
                        logger.warning(
                            f"Transaction {tx_hash} not found in block {block_number}"
                        )
                        tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
                        job_manager.set_transaction_result(
                            tx_hash, tx_receipt["status"] == 1
                        )
                    else:
                        # Transaction found in block, we set the result
                        job_manager.set_transaction_result(
                            tx_hash, block_receipts_hashes[tx_hash] == 1
                        )

                    # Remove transaction from the block's set
                    job_manager.remove_transaction(tx_hash, block_number)

        # Get transactions whose block numbers are higher than the latest finalized block
        n_future_transactions = job_manager.count_transactions_to_confirm(
            block_number + 1, "inf"
        )
        logger.info(
            f"Transactions awaiting for block finality: {n_future_transactions}"
        )

        # Update the latest confirmed block
        logger.info(f"Updating latest confirmed block to {block_number}")
        job_manager.set_latest_confirmed_block(block_number)


@celery.task(bind=True, default_retry_delay=10, max_retries=5)
def send_transaction_result_to_middleware(self: Task, tx_hash: str, result: bool):
    """
    Send the transaction verification result back to the middleware.

    Args:
        tx_hash (str): Transaction hash
        result (bool): Verification result
    """
    try:
        response = requests.post(
            f"{settings.middleware_base_url.rstrip("/")}/callback/evm",
            json=TransactionResultIn(
                transaction_hash=tx_hash, result=result
            ).model_dump(),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"Error sending transaction result to middleware: {exc}")
        self.retry(exc=exc, countdown=2**self.request.retries)
    else:
        logger.info(
            f"Transaction {tx_hash} verification result sent back to middleware"
        )
