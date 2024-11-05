# -*- coding: utf-8 -*-
from pathlib import Path
from sys import argv
from typing import List

import matplotlib.pyplot as plt
import pandas as pd

CONTAINER_STATS_COLUMNS = [
    "timestamp",
    "container_name",
    "cpu_usage_mcpu",
    "memory_usage_mb",
    "memory_limit_mb",
]
RESULTS_COLUMNS = ["timestamp", "tx_hash", "result"]


def load_csv(fname: str | Path, columns: List[str] = None) -> pd.DataFrame:
    # If we provide column names, we assume that the file has no header
    if columns:
        return pd.read_csv(fname, names=columns)
    return pd.read_csv(fname)


if __name__ == "__main__":
    if len(argv) != 3:
        print(
            "Usage: python analyze_load_test_results.py <container_stats_file> <results_file>"
        )
        exit(1)

    # Check if both files exist
    container_stats_file = Path(argv[1])
    results_file = Path(argv[2])
    if not container_stats_file.exists():
        print(f"File {container_stats_file} does not exist")
        exit(1)
    if not results_file.exists():
        print(f"File {results_file} does not exist")
        exit(1)

    # Load CSV files
    container_stats = load_csv(container_stats_file, CONTAINER_STATS_COLUMNS)
    results = load_csv(results_file, RESULTS_COLUMNS)

    # Group container stats by timestamp and sum resources, excluding the "container_name" column
    container_stats = container_stats.groupby("timestamp").sum()
    container_stats.drop(columns=["container_name", "memory_limit_mb"], inplace=True)
    container_stats.reset_index(inplace=True)

    # Aggregate both dataframes by second
    container_stats["timestamp"] = pd.to_datetime(
        container_stats["timestamp"], unit="s"
    )
    results["timestamp"] = pd.to_datetime(results["timestamp"], unit="s")

    container_stats = container_stats.groupby(
        pd.Grouper(key="timestamp", freq="s")
    ).mean()
    results = results.groupby(pd.Grouper(key="timestamp", freq="s")).count()

    # Merge both dataframes
    merged = pd.merge(
        container_stats, results, left_index=True, right_index=True, how="outer"
    )

    # Rollback timestamp to UNIX seconds
    merged.reset_index(inplace=True)
    merged["timestamp"] = merged["timestamp"].astype(int) // 10**9

    # Deduct minimum timestamp to start from 0
    merged["timestamp"] -= merged["timestamp"].min()
    print(merged)

    # Scatter plot the resources and bar plot the number of transactions per second. Add multiple
    # y-axes and legends to the plot
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.scatter(
        merged["timestamp"],
        merged["cpu_usage_mcpu"],
        color="red",
        label="CPU Usage (mCPU)",
    )
    ax1.scatter(
        merged["timestamp"],
        merged["memory_usage_mb"],
        color="blue",
        label="Memory Usage (MB)",
    )
    ax2.bar(
        merged["timestamp"],
        merged["tx_hash"],
        color="green",
        alpha=0.5,
        label="Transactions per second",
    )
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Resources", color="black")
    ax2.set_ylabel("Transactions per second", color="black")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.show()
