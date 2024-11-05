# -*- coding: utf-8 -*-
"""
This load test script is not meant to be ready-to-go. It is a starting point for you to build upon.
"""

import asyncio
import random
from threading import Event, Thread
from time import sleep, time
from typing import Dict, List

import aiohttp
import docker
from fastapi import FastAPI, Response
from loguru import logger
from web3 import Web3

from app.config import settings
from app.pydantic_models import TransactionResultIn, VerifyTransactionIn

TX_RATE = 15  # Transactions per second
BURST_MAX_DURATION = 5 * 60  # 5 minutes
TOTAL_MAX_DURATION = 15 * 60  # 15 minutes
N_BLOCKS = 64  # Number of blocks to fetch transactions from

web3 = Web3(Web3.HTTPProvider(settings.eth_node_url))
app_url = "http://localhost:8080/tx/verify"
callback_app = FastAPI()
docker_client = docker.from_env()
stop_event = Event()


@callback_app.post("/callback/evm")
async def callback_evm(input_data: TransactionResultIn):
    # Write the result to a CSV file
    with open("results.csv", "a") as f:
        f.write(f"{time()},{input_data.transaction_hash},{input_data.result}\n")
    return Response(status_code=204)


def get_container_stats(container_name: str):
    container = docker_client.containers.get(container_name)
    stats = container.stats(stream=False)

    # Calculate CPU usage in mCPU
    cpu_delta = (
        stats["cpu_stats"]["cpu_usage"]["total_usage"]
        - stats["precpu_stats"]["cpu_usage"]["total_usage"]
    )
    system_cpu_delta = (
        stats["cpu_stats"]["system_cpu_usage"]
        - stats["precpu_stats"]["system_cpu_usage"]
    )

    # Check if 'percpu_usage' is available; otherwise, assume 1 CPU
    num_cpus = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))

    if system_cpu_delta > 0 and num_cpus > 0:
        cpu_usage_percent = (cpu_delta / system_cpu_delta) * num_cpus * 100
        cpu_usage_mcpu = cpu_usage_percent * 10  # Convert to mCPU (1 CPU = 1000 mCPU)
    else:
        cpu_usage_mcpu = 0

    # Get memory usage in MB
    memory_usage_mb = stats["memory_stats"]["usage"] / (1024**2)
    memory_limit_mb = stats["memory_stats"]["limit"] / (1024**2)

    return {
        "cpu_usage_mcpu": cpu_usage_mcpu,
        "memory_usage_mb": memory_usage_mb,
        "memory_limit_mb": memory_limit_mb,
    }


def get_transactions(block_number: int):
    block = web3.eth.get_block(block_number, full_transactions=True)
    transactions = []
    for tx in block.transactions:
        transactions.append(
            {
                "from_address": tx["from"],
                "to_address": tx["to"],
                "amount": tx["value"],
                "transaction_hash": tx["hash"].hex(),
            }
        )
    return transactions


async def send_transaction(session: aiohttp.ClientSession, transaction: dict):
    payload = VerifyTransactionIn(**transaction).model_dump()
    async with session.post(app_url, json=payload) as response:
        if response.status != 204:
            logger.error(f"Failed to send transaction: {await response.text()}")


async def load_test(transactions: List[Dict[str, str | int]]):
    async with aiohttp.ClientSession() as session:
        start_time = time()
        tasks = []
        for tx in transactions:
            batch_start = time()
            if time() - start_time > BURST_MAX_DURATION:
                break
            tasks.append(send_transaction(session, tx))
            logger.debug(f"Sent transaction: {tx}")
            if len(tasks) % TX_RATE == 0:
                asyncio.gather(*tasks)
                tasks = []
                await asyncio.sleep(max(0, 1 - (time() - batch_start)))

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)


def log_containers_performance():
    container_names = [
        "starfish-evm-connector-redis",
        "starfish-evm-connector-example-callback",
        "starfish-evm-connector-celery-beat",
        "starfish-evm-connector-celery-worker",
        "starfish-evm-connector-api",
    ]
    while not stop_event.is_set():
        start = time()
        for container_name in container_names:
            stats = get_container_stats(container_name)
            with open("container_stats.csv", "a") as f:
                f.write(
                    f"{start},{container_name},{stats['cpu_usage_mcpu']},{stats['memory_usage_mb']},{stats['memory_limit_mb']}\n"
                )
        sleep(max(0, 1 - (time() - start)))


def trigger_event():
    sleep(TOTAL_MAX_DURATION)
    stop_event.set()


if __name__ == "__main__":
    # Fetch transactions from blocks to simulate load
    logger.info("Fetching transactions...")
    latest_block = web3.eth.block_number
    transactions = []
    start = time()
    for block in range(latest_block, latest_block - N_BLOCKS, -1):
        transactions.extend(get_transactions(block))
        elapsed = time() - start
        got_blocks = latest_block - block + 0.0000000000001
        average_time_per_block = elapsed / got_blocks
        eta = average_time_per_block * (N_BLOCKS - got_blocks)
        logger.info(
            f"Blocks remaining: {N_BLOCKS - (latest_block - block)}, ETA: {eta:.0f} s"
        )
    random.shuffle(transactions)  # Shuffle for load testing

    # Periodically log containers' performance
    performance_thread = Thread(target=log_containers_performance)
    performance_thread.start()

    # Start the event trigger thread
    trigger_thread = Thread(target=trigger_event)
    trigger_thread.start()

    # Start the load test
    logger.info("Starting load test...")
    asyncio.run(load_test(transactions))
    logger.info("Load test completed.")

    # Wait for threads to finish
    logger.info("Waiting for threads to finish...")
    performance_thread.join()
    trigger_thread.join()
