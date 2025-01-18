# -*- coding: utf-8 -*-

from middleware.config import settings
from middleware.contracts import invoke, query


async def add_peer_to_whitelist(
    peer_address: str, *, namespace: str = "default"
) -> None:
    """
    Adds a peer to the whitelist

    Args:
        peer_address (str): The address of the peer
        namespace (str, optional): The namespace of the contract. Defaults to "default".
    """
    await invoke(
        api_name=settings.listrack_contract_api_name,
        method="addMiddlewareNode",
        namespace=namespace,
        parameters={
            "_middlewareNode": peer_address,
        },
    )


async def get_contract_owner(*, namespace: str = "default") -> str:
    """
    Returns the address of the contract owner

    Args:
        namespace (str, optional): The namespace of the contract. Defaults to "default".

    Returns:
        str: The address of the contract owner
    """
    return (
        await query(
            api_name=settings.listrack_contract_api_name,
            method="owner",
            namespace=namespace,
        )
    )["output"]


async def get_trade_id_by_transaction_hash(
    transaction_hash: str, *, namespace: str = "default"
) -> str:
    """
    Returns the trade ID by transaction hash

    Args:
        transaction_hash (str): The transaction hash
        namespace (str, optional): The namespace of the contract. Defaults to "default".

    Returns:
        str: The trade ID
    """
    return (
        await query(
            api_name=settings.listrack_contract_api_name,
            method="getTradeIdByTransactionHash",
            namespace=namespace,
            parameters={"_ethTransactionHash": transaction_hash},
        )
    )["output"]


async def settle_trade(
    trade_id: str, confirmed: bool, *, namespace: str = "default"
) -> None:
    """
    Settles a trade
    """
    await invoke(
        api_name=settings.listrack_contract_api_name,
        method="settleTrade",
        namespace=namespace,
        parameters={
            "tradeId": trade_id,
            "confirmed": confirmed,
        },
    )
