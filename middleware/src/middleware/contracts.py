# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import aiohttp
import orjson as json
from loguru import logger

from middleware.utils import build_firefly_url, to_kebab_case


async def deploy_contract(
    contract_json: str | Path | Dict,
    *,
    namespace: str = "default",
    api_name: str = None,
) -> str:
    """
    Deploys a smart contract to the blockchain, a FireFly interface and an HTTP API for it.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        contract_json (str | Path | Dict): Path to the contract JSON file or the contract JSON object.
        namespace (str): The namespace to deploy the contract to.
        api_name (str): The name of the FireFly HTTP API to be created.

    Returns:
        str: The HTTP API name to use.
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

    return api_name


async def call(
    *,
    api_name: str,
    api_method: str,
    method: str,
    parameters: Dict[str, Any],
    options: Dict[str, Any] = None,
    namespace: str = "default",
) -> Dict:
    """
    Calls a smart contract function through the HTTP API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str): The name of the HTTP API to invoke.
        api_method (str): Either "invoke" or "query".
        method (str): The method of the smart contract to invoke.
        parameters (Dict[str, Any]): The parameters to pass to the contract function.
        options (Dict[str, Any]): Additional options to pass to the contract function.
        namespace (str): The namespace to deploy the contract to.

    Returns:
        Dict: The result of the contract function.
    """
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
    api_name: str,
    *,
    method: str,
    parameters: Dict[str, Any],
    options: Dict[str, Any] = None,
    namespace: str = "default",
) -> Dict:
    """
    Invokes a smart contract function through the HTTP API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str): The name of the HTTP API to invoke.
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
    api_name: str,
    *,
    method: str,
    parameters: Dict[str, Any],
    options: Dict[str, Any] = None,
    namespace: str = "default",
):
    """
    Queries a smart contract function through the HTTP API.
    Ref: https://hyperledger.github.io/firefly/latest/tutorials/custom_contracts/ethereum/

    Args:
        api_name (str): The name of the HTTP API to invoke.
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
