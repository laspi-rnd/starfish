# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict
from uuid import NAMESPACE_DNS, uuid5

import aiohttp
import orjson as json
from loguru import logger

from middleware.enums import FireFlyUrlTypeEnum
from middleware.messaging import subscribe_to_websocket
from middleware.pydantic_models import FireFlySmartContract
from middleware.types import JSONSerializable
from middleware.utils import build_firefly_url, to_kebab_case


async def deploy_contract(
    contract_json: str | Path | Dict,
    *,
    namespace: str = "default",
    api_name: str = None,
) -> FireFlySmartContract:
    """
    Deploys a smart contract to the blockchain, a FireFly interface and an HTTP API for it.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        contract_json (str | Path | Dict): Path to the contract JSON file or the contract JSON object.
        namespace (str): The namespace to deploy the contract to.
        api_name (str): The name of the FireFly HTTP API to be created.

    Returns:
        FireFlySmartContract: The FireFly smart contract object, containing all information about
            the deployed smart contract.
    """
    # If it's a string, we can try to parse it as a JSON and then as a file
    if isinstance(contract_json, str):
        try:
            contract_json = json.loads(contract_json)
        except json.JSONDecodeError:
            contract_json = Path(contract_json)

    # If it's a file, we must read it
    if isinstance(contract_json, Path):
        if not contract_json.exists():
            raise FileNotFoundError(f"Contract JSON file not found at {contract_json}")
        with contract_json.open() as file:
            contract_json: Dict = json.loads(file.read())

    # Sanity check: the contract must have enough fields for deployment
    if (
        "abi" not in contract_json
        or "bytecode" not in contract_json
        or "contractName" not in contract_json
    ):
        raise ValueError(
            "Invalid contract JSON: missing 'abi', 'bytecode' or 'contractName' fields"
        )

    # Actually deploy the contract
    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/contracts/deploy?confirm=true"
    )
    json_data = {
        "contract": contract_json["bytecode"],
        "definition": contract_json["abi"],
        "input": [],
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
            response_data = await response.json()
            address = response_data["output"]["contractLocation"]["address"]

    logger.debug(f"Contract deployed at address: {address}")

    # Generate the FireFly interface for this contract
    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/contracts/interfaces/generate"
    )
    json_data = {
        "input": {
            "abi": contract_json["abi"],
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
            response_data = await response.json()

    logger.debug("Successfully generated FireFly interface for the contract")

    # Broadcast the FireFly interface to the network
    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/contracts/interfaces?publish=true&confirm=true"
    )
    json_data = {
        **response_data,
        "name": contract_json["contractName"],
        "version": datetime.now().strftime("%Y%m%d%H%M%S"),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
            response_data = await response.json()
            interface_id = response_data["id"]

    logger.debug(
        f"Successfully broadcasted the FireFly interface to the network with id {interface_id}"
    )

    # Create an HTTP API for the contract
    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/apis?publish=true&confirm=true"
    )
    json_data = {
        "name": api_name or to_kebab_case(contract_json["contractName"]),
        "interface": {
            "id": interface_id,
        },
        "location": {
            "address": address,
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
            response_data = await response.json()
            api_name = response_data["name"]

    logger.debug(
        f"Successfully created the HTTP API for the contract with name {api_name}"
    )

    return FireFlySmartContract(
        blockchain_address=address, interface_id=interface_id, api_name=api_name
    )


async def get_contract(
    api_name: str | FireFlySmartContract,
    *,
    namespace: str = "default",
) -> FireFlySmartContract | None:
    """
    Gets the information of a smart contract from the blockchain.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str | FireFlySmartContract): The name of the HTTP API to get the contract information.
        namespace (str): The namespace to deploy the contract to.

    Returns:
        FireFlySmartContract | None: The FireFly smart contract object, containing all information about
            the deployed smart contract, or None if the contract does not exist.
    """
    if isinstance(api_name, FireFlySmartContract):
        api_name = api_name.api_name

    url = build_firefly_url(path=f"/api/v1/namespaces/{namespace}/apis/{api_name}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            response_data = await response.json()

    return FireFlySmartContract(
        blockchain_address=response_data["location"]["address"],
        interface_id=response_data["interface"]["id"],
        api_name=api_name,
    )


async def call(
    *,
    api_name: str | FireFlySmartContract,
    api_method: str,
    method: str,
    parameters: Dict[str, Any] = None,
    options: Dict[str, Any] = None,
    namespace: str = "default",
) -> Dict:
    """
    Calls a smart contract function through the HTTP API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str | FireFlySmartContract): The name of the HTTP API to invoke.
        api_method (str): Either "invoke" or "query".
        method (str): The method of the smart contract to invoke.
        parameters (Dict[str, Any]): The parameters to pass to the contract function.
        options (Dict[str, Any]): Additional options to pass to the contract function.
        namespace (str): The namespace to deploy the contract to.

    Returns:
        Dict: The result of the contract function.
    """
    if isinstance(api_name, FireFlySmartContract):
        api_name = api_name.api_name

    if api_method not in ("invoke", "query"):
        raise ValueError(f"Unsupported API method: {api_method}")

    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/apis/{api_name}/{api_method}/{method}?confirm=true"
    )
    json_data = {
        "input": parameters,
        "location": None,
    }
    if options:
        json_data["options"] = options
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            response.raise_for_status()
            response_data = await response.json()

    return response_data


async def invoke(
    api_name: str | FireFlySmartContract,
    *,
    method: str,
    parameters: Dict[str, Any] = None,
    options: Dict[str, Any] = None,
    namespace: str = "default",
) -> Dict:
    """
    Invokes a smart contract function through the HTTP API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str | FireFlySmartContract): The name of the HTTP API to invoke.
        method (str): The method of the smart contract to invoke.
        parameters (Dict[str, Any]): The parameters to pass to the contract function.
        options (Dict[str, Any]): Additional options to pass to the contract function.
        namespace (str): The namespace to deploy the contract to.

    Returns:
        Dict: The result of the contract function.
    """
    return await call(
        api_name=api_name,
        api_method="invoke",
        method=method,
        parameters=parameters,
        options=options,
        namespace=namespace,
    )


async def query(
    api_name: str | FireFlySmartContract,
    *,
    method: str,
    parameters: Dict[str, Any] = None,
    options: Dict[str, Any] = None,
    namespace: str = "default",
):
    """
    Queries a smart contract function through the HTTP API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str | FireFlySmartContract): The name of the HTTP API to invoke.
        method (str): The method of the smart contract to invoke.
        parameters (Dict[str, Any]): The parameters to pass to the contract function.
        options (Dict[str, Any]): Additional options to pass to the contract function.
        namespace (str): The namespace to deploy the contract to.

    Returns:
        Dict: The result of the contract function.
    """
    return await call(
        api_name=api_name,
        api_method="query",
        method=method,
        parameters=parameters,
        options=options,
        namespace=namespace,
    )


async def listen_events(
    contract: FireFlySmartContract,
    event_name: str,
    on_message: Callable[[JSONSerializable], Awaitable[None]],
    *,
    namespace: str = "default",
) -> asyncio.Task:
    """
    Creates an event listener for a smart contract and starts listening to it.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        contract (FireFlySmartContract): The FireFly smart contract object.
        event_name (str): The name of the event to listen for.
        on_message (Callable[[JSONSerializable], Awaitable[None]]): The callback to call for each event.
        namespace (str): The namespace to deploy the contract to.

    Returns:
        asyncio.Task: The task for the event listener.
    """
    # Create an event listener for the contract
    app_identifier_content = [namespace, contract.blockchain_address, event_name]
    app_identifier_content = "_".join(app_identifier_content)
    app_identifier = f"middleware_{uuid5(NAMESPACE_DNS, app_identifier_content)}"
    url = build_firefly_url(
        path=f"/api/v1/namespaces/{namespace}/contracts/listeners?confirm=true&publish=true"
    )
    json_data = {
        "filters": [
            {
                "interface": {
                    "id": contract.interface_id,
                },
                "location": {
                    "address": contract.blockchain_address,
                },
                "eventPath": event_name,
            }
        ],
        "options": {
            "firstEvent": "newest",
        },
        "topic": app_identifier,
        "name": app_identifier,
    }
    listener_id = None
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
            if response.status == 409:
                # If the listener already exists, we need to get its ID
                url = build_firefly_url(
                    path=f"/api/v1/namespaces/{namespace}/contracts/listeners/{app_identifier}"
                )
                async with session.get(url) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    listener_id = response_data["id"]
            elif response.status >= 200 and response.status < 300:
                response_data = await response.json()
                listener_id = response_data["id"]
            else:
                response.raise_for_status()
    if not listener_id:
        raise ValueError("Failed to create event listener")

    logger.debug(
        f"Successfully created event listener for event {event_name} with id {listener_id}"
    )

    # Create a subscription for the event listener
    url = build_firefly_url(path=f"/api/v1/namespaces/{namespace}/subscriptions")
    json_data = {
        "namespace": namespace,
        "name": app_identifier,
        "transport": "websockets",
        "filter": {
            "events": "blockchain_event_received",
            "blockchainevent": {
                "listener": listener_id,
            },
        },
        "options": {
            "firstEvent": "oldest",
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=json.dumps(json_data),
            headers={"accept": "application/json", "content-type": "application/json"},
        ) as response:
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
