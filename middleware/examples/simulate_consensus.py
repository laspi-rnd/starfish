# -*- coding: utf-8 -*-
import json
from copy import deepcopy
from enum import Enum
from queue import Queue
from random import random
from threading import Thread, Lock
from time import sleep

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import networkx as nx
from loguru import logger


GLOBAL_COUNTER = 0
GLOBAL_COUNTER_LOCK = Lock()
N_NODES = 3
NONCE_MAX = 3
STATE_TIMEOUT = 5
VOTE_TRUE_PROBABILITY = 0.8
STOP_PROCESSING = False  # Global stop flag


class MessageType(Enum):
    EVENT_FROM_BLOCKCHAIN = 1
    NODE_SENT_VOTE = 2
    NODE_SENT_RESULT = 3


EVENT_STATE: dict[str, dict] = {}
for i in range(N_NODES):
    EVENT_STATE[f"NODE_{i + 1}"] = {}

MESSAGE_BUS: dict[str, list] = {}
for i in range(N_NODES):
    MESSAGE_BUS[f"NODE_{i + 1}"] = []

# Queue for image generation tasks
image_queue = Queue()


def format_message_for_image(message: dict) -> str:
    if message["type"] == MessageType.EVENT_FROM_BLOCKCHAIN:
        return "Event from blockchain"
    elif message["type"] == MessageType.NODE_SENT_VOTE:
        return f"Vote: {message['vote']}, Weight: {message['coord']}"
    elif message["type"] == MessageType.NODE_SENT_RESULT:
        return f"Result: {message['result']}"
    return ""


def add_message_to_bus(
    *, from_node_id: str, node_id: str, message: dict, from_broadcast: bool = False
) -> None:
    MESSAGE_BUS[node_id].append({**message, "from": from_node_id})
    if not from_broadcast:
        image_queue.put(
            [
                {
                    "from": from_node_id,
                    "to": node_id,
                    "text": format_message_for_image(message),
                    "current_state": deepcopy(EVENT_STATE),
                }
            ]
        )


def broadcast(*, from_node_id: str, message: dict) -> None:
    image_queue_messages = []
    current_state = deepcopy(EVENT_STATE)
    for node_id in MESSAGE_BUS:
        if node_id != from_node_id:
            add_message_to_bus(
                from_node_id=from_node_id,
                node_id=node_id,
                message=message,
                from_broadcast=True,
            )
            image_queue_messages.append(
                {
                    "from": from_node_id,
                    "to": node_id,
                    "text": format_message_for_image(message),
                    "current_state": deepcopy(current_state),
                }
            )
    image_queue.put(image_queue_messages)


def get_vote() -> bool:
    return random() <= VOTE_TRUE_PROBABILITY


def process_message(*, node_id: str) -> None:
    if len(MESSAGE_BUS[node_id]) == 0:
        logger.debug(f"{node_id}\t| No messages for {node_id}")
        return

    message = MESSAGE_BUS[node_id].pop(0)
    message_type = message["type"]
    logger.debug(f"{node_id}\t| Processing message {message} for {node_id}")

    if message_type == MessageType.EVENT_FROM_BLOCKCHAIN:
        coordinator_weight = random()
        vote = get_vote()
        EVENT_STATE[node_id] = {
            "coordinator_weights": {
                node_id: coordinator_weight,
            },
            "votes": {
                node_id: vote,
            },
        }
        sleep(random())
        logger.debug(
            f"{node_id}\t| Broadcasting vote {vote} and weight {coordinator_weight}"
        )
        broadcast(
            from_node_id=node_id,
            message={
                "type": MessageType.NODE_SENT_VOTE,
                "coord": coordinator_weight,
                "vote": vote,
            },
        )

    elif message_type == MessageType.NODE_SENT_VOTE:
        coord = message["coord"]
        vote = message["vote"]

        EVENT_STATE[node_id]["coordinator_weights"][message["from"]] = coord
        EVENT_STATE[node_id]["votes"][message["from"]] = vote

        logger.debug(
            f"{node_id}\t| Received vote {vote} and weight {coord} from {message['from']}"
        )

        if len(EVENT_STATE[node_id]["coordinator_weights"]) == N_NODES:
            logger.debug(f"{node_id}\t| All votes received for event")

            # Choose the coordinator with the highest weight
            max_weight = max(EVENT_STATE[node_id]["coordinator_weights"].values())
            coordinator = [
                k
                for k, v in EVENT_STATE[node_id]["coordinator_weights"].items()
                if v == max_weight
            ][0]
            logger.debug(f"{node_id}\t| Coordinator chosen: {coordinator}")

            # Choose result based on majority vote
            votes = list(EVENT_STATE[node_id]["votes"].values())
            vote = sum(votes) >= N_NODES / 2
            logger.debug(f"{node_id}\t| Final vote: {vote}")

            EVENT_STATE[node_id]["coordinator"] = coordinator
            EVENT_STATE[node_id]["result"] = vote

            sleep(random())
            logger.debug(
                f"{node_id}\t| Broadcasting result {vote} to coordinator {coordinator}"
            )
            add_message_to_bus(
                from_node_id=node_id,
                node_id=coordinator,
                message={
                    "type": MessageType.NODE_SENT_RESULT,
                    "result": vote,
                    "coordinator": coordinator,
                    "nonce": 1,
                    "originally_from": node_id,
                },
            )

    elif message_type == MessageType.NODE_SENT_RESULT:
        if message["originally_from"] == node_id:
            return

        if message["nonce"] > NONCE_MAX:
            return

        result = message["result"]
        coordinator = message["coordinator"]

        my_coordinator = EVENT_STATE[node_id]["coordinator"]

        if coordinator != my_coordinator:
            logger.debug(
                f"{node_id}\t| The coordinator {coordinator} is not the same as my coordinator {my_coordinator}. I'm forwarding the result."
            )
            add_message_to_bus(
                from_node_id=node_id,
                node_id=my_coordinator,
                message={
                    "type": MessageType.NODE_SENT_RESULT,
                    "result": result,
                    "coordinator": coordinator,
                    "nonce": message["nonce"] + 1,
                    "originally_from": message["originally_from"],
                },
            )
            return

        if coordinator != node_id:
            logger.debug(
                f"{node_id}\t| I'm not the coordinator. I'm finishing my processing."
            )
            EVENT_STATE[node_id]["stop_processing"] = True
            return

        my_result = EVENT_STATE[node_id]["result"]
        if "results" not in EVENT_STATE[node_id]:
            EVENT_STATE[node_id]["results"] = {
                node_id: my_result,
            }
        EVENT_STATE[node_id]["results"][message["from"]] = result
        logger.debug(
            f"{node_id}\t| Received result {result} from {message['from']} for event"
        )

        if len(EVENT_STATE[node_id]["results"]) == N_NODES:
            logger.debug(f"{node_id}\t| All results received for event")
            final_result = sum(EVENT_STATE[node_id]["results"].values()) >= N_NODES / 2
            logger.success(f"Final result for event: {final_result}")
            global STOP_PROCESSING
            STOP_PROCESSING = True  # Set the stop flag
            image_queue.put([])  # Optionally trigger image generation


def process_message_loop(*, node_id: str) -> None:
    while not STOP_PROCESSING:  # Check the stop condition
        process_message(node_id=node_id)
        sleep(random())


def draw_blockchain(ax):
    """Draw a flat rectangle to represent the blockchain."""
    blockchain_rect = patches.Rectangle(
        (0.35, 0.05), 0.3, 0.1, linewidth=1, edgecolor="black", facecolor="lightgray"
    )
    ax.add_patch(blockchain_rect)
    ax.text(
        0.5,
        0.1,
        "Blockchain",
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=10,
        color="black",
    )


def draw_node_state(ax, pos, node_id, state):
    """Draw a text box below the node to show its state."""
    x, y = pos[node_id]
    state_text = (
        f"{node_id} State:\n{json.dumps(state, indent=2)}"  # Pretty-print JSON state
    )
    ax.text(
        x,
        y - 0.1,  # Position the state text below the node
        state_text,
        fontsize=8,
        bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.3"),
        ha="left",  # Change to left align text
        va="top",  # Align text to the top
    )


def draw_message_arrow(ax, from_pos, to_pos, message):
    """Draw an arrow with a message label between nodes."""
    ax.annotate(
        "",
        xy=to_pos,
        xytext=from_pos,
        arrowprops=dict(arrowstyle="->", color="blue", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.3", fc="w"),
    )
    mid_x, mid_y = (from_pos[0] + to_pos[0]) / 2, (from_pos[1] + to_pos[1]) / 2
    ax.text(
        mid_x,
        mid_y,
        message,
        fontsize=8,
        color="blue",
        bbox=dict(facecolor="white", edgecolor="blue", boxstyle="round,pad=0.3"),
    )


def generate_image(messages):
    """Main function to generate the network diagram with blockchain, nodes, and messages."""

    G = nx.DiGraph()

    # Add nodes to graph
    node_list = ["NODE_1", "NODE_2", "NODE_3"]
    G.add_nodes_from(node_list)

    # Use a fixed position for each node, spread out more
    pos = {
        "NODE_1": (0.2, 0.6),
        "NODE_2": (0.5, 0.4),
        "NODE_3": (0.8, 0.6),
    }

    # Get current state
    current_state: dict = messages[0]["current_state"]

    # Calculate max state length for figure size
    max_state_length = max(
        len(json.dumps(state, indent=2)) for state in current_state.values()
    )  # Calculate max state length
    fig_width = 10 + (max_state_length // 50) + 1  # Adjust width based on state length
    fig_height = (
        6 + (len(node_list) * 0.5) + 1
    )  # Adjust height based on number of nodes

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))  # Create figure and axes

    # Draw the blockchain
    draw_blockchain(ax)

    # Draw the nodes
    nx.draw(G, pos, with_labels=True, node_size=2000, node_color="lightblue", ax=ax)

    # Draw the state of each node below it
    for node_id, state in current_state.items():
        draw_node_state(ax, pos, node_id, state)

    # Draw the messages as arrows
    for message in messages:
        from_node = message["from"]
        to_node = message["to"]
        text = message["text"]

        if from_node == "NULL":
            from_pos = (0.5, 0.1)  # Blockchain position
        else:
            from_pos = pos[from_node]

        to_pos = pos[to_node]
        draw_message_arrow(ax, from_pos, to_pos, text)

    with GLOBAL_COUNTER_LOCK:
        global GLOBAL_COUNTER
        image_name = f"image_{GLOBAL_COUNTER}.png"
        GLOBAL_COUNTER += 1
        plt.savefig(image_name)


def image_generation_loop():
    while True:
        messages = image_queue.get()
        generate_image(messages)


def simulate_consensus(nodes, states):
    """Simulate the consensus algorithm and generate images."""
    num_nodes = len(nodes)
    max_state_length = max(
        len(json.dumps(state, indent=2)) for state in states
    )  # Calculate max state length
    fig_width = 10 + (max_state_length // 50)  # Adjust width based on state length
    fig_height = 5 + (num_nodes * 0.5)  # Adjust height based on number of nodes

    plt.figure(figsize=(fig_width, fig_height))  # Set figure size

    # ... existing code ...


# ... existing code ...

if __name__ == "__main__":
    # Start the image generation thread
    img_thread = Thread(target=image_generation_loop, daemon=True)
    img_thread.start()

    # Start message processing threads for nodes
    threads: list[Thread] = []
    for node_id in MESSAGE_BUS:
        t = Thread(target=process_message_loop, kwargs={"node_id": node_id})
        t.start()
        threads.append(t)

    # Trigger initial broadcast
    broadcast(
        from_node_id="NULL",
        message={
            "type": MessageType.EVENT_FROM_BLOCKCHAIN,
        },
    )

    for t in threads:
        t.join()  # Wait for all threads to finish

    print("All nodes have finished processing. Exiting script.")
