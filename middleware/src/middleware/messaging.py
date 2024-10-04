# -*- coding: utf-8 -*-
import asyncio
from typing import Awaitable, Callable, List
from uuid import NAMESPACE_DNS, uuid5

import aiohttp
import orjson as json
import websockets
from loguru import logger

from middleware.enums import FireFlyUrlTypeEnum
from middleware.types import JSONSerializable
from middleware.utils import build_firefly_url


async def broadcast(
    data: JSONSerializable,
    *,
    namespace: str = "default",
    tag: str = None,
    topics: List[str] = None,
) -> JSONSerializable:
    """
    Broadcast data to the FireFly API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/broadcast_data

    Args:
        data (JSONSerializable): The data to broadcast.
        namespace (str): The namespace to broadcast to.
        tag (str): An optional tag to include in the message.
        topics (List[str]): An optional list of topics to include in the message.

    Returns:
        JSONSerializable: The response from the FireFly API.
    """
    url = build_firefly_url(path=f"/api/v1/namespaces/{namespace}/messages/broadcast")
    json_data = {
        "data": [
            {
                "value": data,
                "validator": "json",
            }
        ]
    }
    if tag:
        if "header" not in json_data:
            json_data["header"] = {}
        json_data["header"]["tag"] = tag
    if topics:
        if "header" not in json_data:
            json_data["header"] = {}
        json_data["header"]["topics"] = topics
    logger.debug(f"Broadcasting data: {json_data}")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            logger.warning(f"Broadcast response: {await response.text()}")
            response.raise_for_status()
            response_data = await response.json()
            return response_data


async def get_message_by_id(
    message_id: str,
    *,
    namespace: str = "default",
) -> JSONSerializable:
    """
    Get a message by its ID from the FireFly API.

    Args:
        message_id (str): The ID of the message to get.
        namespace (str): The namespace to get the message from.

    Returns:
        JSONSerializable: The message contents.
    """
    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/messages/{message_id}?fetchdata=true"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            response_data = await response.json()
            return response_data


async def listen_messages(
    on_message: Callable[[JSONSerializable], Awaitable[None]],
    *,
    namespace: str = "default",
    tag: str = None,
    topics: List[str] = None,
) -> asyncio.Task:
    """
    Listen for messages from the FireFly API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/events

    Args:
        on_message (Callable[[JSONSerializable], Awaitable[None]]): The callback to call for each message.
        namespace (str): The namespace to listen to.
        tag (str): An optional tag to filter messages by.
        topics (List[str]): An optional list of topics to filter messages by.

    Returns:
        asyncio.Task: The task that listens for messages.
    """
    # First we set up the websocket subscription
    uri = build_firefly_url(f"/api/v1/namespaces/{namespace}/subscriptions")
    app_identifier_content = (
        [namespace] + [tag] if tag else [] + topics if topics else []
    )
    app_identifier_content = "_".join(app_identifier_content)
    app_identifier = f"middleware_{uuid5(NAMESPACE_DNS, app_identifier_content)}"
    data = {
        "transport": "websockets",
        "name": app_identifier,
        "filter": {
            "message": {
                "author": ".*",
                "group": ".*",
                "tag": tag if tag else ".*",
                "topics": topics if topics else ".*",
            },
            "events": "message_confirmed",
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(uri, json=data) as response:
            if response.status >= 200 and response.status < 300:
                logger.info(
                    f"Created subscription with app identifier: {app_identifier}"
                )
            elif response.status == 409:
                logger.info(
                    f"Subscription already exists with app identifier: {app_identifier}"
                )
            else:
                response.raise_for_status()

    # Then we prepare the callback to handle incoming messages
    async def on_websocket_callback(message_data: JSONSerializable) -> None:
        try:
            logger.debug(f"Received message: {message_data}")
            mid = message_data.get("reference")
            message_data = await get_message_by_id(mid)
            await on_message(message_data)
        except Exception as e:
            logger.error(f"Error in on_websocket_callback: {e}")

    # Finally we subscribe to the websocket
    websocket_uri = build_firefly_url(
        f"/ws?namespace={namespace}&name={app_identifier}",
        url_type=FireFlyUrlTypeEnum.WS,
    )
    return asyncio.create_task(
        subscribe_to_websocket(websocket_uri, on_websocket_callback)
    )


async def send_private_message(
    data: JSONSerializable,
    to_org: str,
    *,
    namespace: str = "default",
    tag: str = None,
    topics: List[str] = None,
) -> JSONSerializable:
    """
    Send a private message to a specific organization via the FireFly API.

    Args:
        data (JSONSerializable): The data to send.
        to_org (str): The organization to send the message to.
        namespace (str): The namespace to send the message from.
        tag (str): An optional tag to include in the message.
        topics (List[str]): An optional list of topics to include in the message.

    Returns:
        JSONSerializable: The response from the FireFly API.
    """
    url = build_firefly_url(path=f"/api/v1/namespaces/{namespace}/messages/private")
    json_data = {
        "data": [
            {
                "value": data,
                "validator": "json",
            }
        ],
        "group": {
            "members": [
                {
                    "identity": to_org,
                }
            ]
        },
    }
    if tag:
        if "header" not in json_data:
            json_data["header"] = {}
        json_data["header"]["tag"] = tag
    if topics:
        if "header" not in json_data:
            json_data["header"] = {}
        json_data["header"]["topics"] = topics
    logger.debug(f"Sending private message to {to_org}: {json_data}")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
            response_data = await response.json()
            return response_data


async def subscribe_to_websocket(
    uri: str,
    on_message: Callable[[JSONSerializable], Awaitable[None]],
) -> None:
    """
    Subscribe to a websocket and call `on_message` for each message.

    Args:
        uri (str): The URI of the websocket to connect to.
        on_message (Callable[[JSONSerializable], Awaitable[None]]): The callback to call for each message.
    """
    reconnect_attempt: int = 0
    while True:
        try:
            # Attempt to connect and listen to the WebSocket
            logger.info(f"Attempting to connect to WebSocket on {uri}...")
            await websocket_listener(uri, on_message)
        except websockets.ConnectionClosedError as e:
            logger.error(f"WebSocket connection closed unexpectedly: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        # Apply exponential backoff strategy for retries
        reconnect_attempt += 1
        backoff_time: int = min(2**reconnect_attempt, 60)  # Cap backoff at 60 seconds
        logger.info(f"Retrying WebSocket connection in {backoff_time} seconds...")
        await asyncio.sleep(backoff_time)


async def websocket_listener(
    uri: str, on_message: Callable[[JSONSerializable], Awaitable[None]]
):
    """
    Listen for messages on a websocket and call `on_message` for each message.

    Args:
        uri (str): The URI of the websocket to connect to.
        on_message (Callable[[JSONSerializable], Awaitable[None]]): The callback to call for each message.
    """
    async with websockets.connect(uri) as websocket:
        while True:
            try:
                message = await websocket.recv()
                message_json: dict = json.loads(message)
                await on_message(message_json)
                # Acknowledge the message
                message_id = message_json.get("id")
                if message_id:
                    await websocket.send(json.dumps({"type": "ack", "id": message_id}))
            except websockets.ConnectionClosed as exc:
                logger.error(f"Websocket connection closed: {exc}")
                break
            except Exception as exc:
                logger.error(f"Error in websocket_listener: {exc}")
                break
