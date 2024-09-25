# -*- coding: utf-8 -*-
from celery import Celery, Task
from celery.exceptions import Retry
from loguru import logger
from web3 import Web3

from app.config import settings
from app.enums import JobStatus
from app.job_manager import job_manager

celery = Celery("tasks", broker=settings.celery_broker_url)
w3 = Web3(Web3.HTTPProvider(settings.eth_node_url))


@celery.task(bind=True)
def verify_transaction(
    self: Task,
    job_id: str,
    from_eth_address: str,
    to_eth_address: str,
    amount: int,
    transaction_hash: str,
) -> None:
    """
    Verify that a transaction has been confirmed by the network.

    Args:
        job_id (str): Job ID
        from_eth_address (str): From Ethereum address
        to_eth_address (str): To Ethereum address
        amount (int): Amount to transfer
        transaction_hash (str): Transaction hash
    """
    try:
        tx = w3.eth.get_transaction(transaction_hash)
        block_diff = w3.eth.block_number - tx["blockNumber"]

        # Check if job has expired
        if not job_manager.is_job_alive(job_id):
            logger.error(f"Job {job_id} has expired")
            job_manager.set_job_status_and_result(job_id, JobStatus.FAILED, None)

        # Check if transaction is finalized
        if block_diff < settings.block_confirmations:
            logger.info(
                f"Transaction {transaction_hash} has not been confirmed yet (block_diff={block_diff})"
            )
            raise self.retry(
                countdown=settings.celery_job_retry_delay,
                max_retries=settings.celery_job_retry_max_retries,
            )

        # Verify sender
        if tx["from"].lower() != from_eth_address.lower():
            logger.error(
                f"Transaction {transaction_hash} was sent by {tx['from']}, expected {from_eth_address}"
            )
            job_manager.set_job_status_and_result(job_id, JobStatus.COMPLETED, False)

        # Verify receiver
        if tx["to"].lower() != to_eth_address.lower():
            logger.error(
                f"Transaction {transaction_hash} was sent to {tx['to']}, expected {to_eth_address}"
            )
            job_manager.set_job_status_and_result(job_id, JobStatus.COMPLETED, False)

        # Verify amount
        if tx["value"] != amount:
            logger.error(
                f"Transaction {transaction_hash} was sent with {tx['value']} wei, expected {amount} wei"
            )
            job_manager.set_job_status_and_result(job_id, JobStatus.COMPLETED, False)

        # Transaction is valid
        logger.info(f"Transaction {transaction_hash} has been confirmed")
        job_manager.set_job_status_and_result(job_id, JobStatus.COMPLETED, True)

    except Retry as exc:
        logger.warning(f"Retrying transaction {transaction_hash}: {exc}")

    except Exception as exc:
        logger.error(f"Error verifying transaction {transaction_hash}: {exc}")
        job_manager.set_job_status_and_result(job_id, JobStatus.FAILED, None)
