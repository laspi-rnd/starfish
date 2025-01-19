# -*- coding: utf-8 -*-
import asyncio
from random import random

from loguru import logger
from pydantic import BaseModel
from redis.asyncio import Redis

from middleware.config import settings
from middleware.connectors.evm import start_verification_job
from middleware.enums import StarfishMessageType
from middleware.listrack import (
    add_peer_to_whitelist,
    get_contract_owner,
    get_trade_id_by_transaction_hash,
    settle_trade,
)
from middleware.messaging import broadcast, send_private_message
from middleware.pydantic_models import (
    CheckTransactionState,
    EventCheckTransaction,
    Message,
    StarfishMessageAskForEthereumAddress,
    StarfishMessageEthereumAddress,
    StarfishMessagePeerSentOwnVote,
    StarfishMessagePeerSentComputedResult,
    VerifyTransactionIn,
)
from middleware.utils import (
    get_my_ethereum_address,
    get_my_org,
    get_nodes_count,
    get_ntp_timestamp,
)

MESSAGE_TO_MODEL = {
    StarfishMessageType.ASK_FOR_ETHEREUM_ADDRESS: StarfishMessageAskForEthereumAddress,
    StarfishMessageType.ETHEREUM_ADDRESS: StarfishMessageEthereumAddress,
    StarfishMessageType.PEER_SENT_OWN_VOTE: StarfishMessagePeerSentOwnVote,
    StarfishMessageType.PEER_SENT_COMPUTED_RESULT: StarfishMessagePeerSentComputedResult,
}


class StateManager:
    def __init__(self):
        self._redis = Redis.from_url(settings.redis_url)

    def _parse_message_content(self, message: Message) -> BaseModel:
        starfish_message_type = message.data.get("type")
        if not starfish_message_type:
            raise ValueError("Message does not have a type")
        model = MESSAGE_TO_MODEL.get(starfish_message_type)
        if not model:
            raise ValueError(
                f"Unsupported Starfish message type: {starfish_message_type}"
            )
        return model(**{k: v for k, v in message.data.items() if k != "type"})

    async def get_peer_address(self, org: str) -> str:
        address = await self._redis.get(f"peer:{org}:address")
        return address.decode() if address else ""

    async def set_peer_address(self, org: str, address: str) -> None:
        await self._redis.set(f"peer:{org}:address", address)

    async def get_state(self, transaction_hash: str) -> CheckTransactionState | None:
        serialized_state = await self._redis.get(f"tx:{transaction_hash}")
        if serialized_state:
            return CheckTransactionState.model_validate_json(serialized_state.decode())
        return None

    async def set_state(
        self, transaction_hash: str, state: CheckTransactionState
    ) -> None:
        serialized_state = state.model_dump_json()
        await self._redis.set(f"tx:{transaction_hash}", serialized_state)

    async def set_transaction_vote(self, transaction_hash: str, vote: bool) -> None:
        # The connector has sent us the result of the transaction verification. We must now collect
        # a random number for our coordinator weight, store these results in our state and broadcast
        # our vote to the other nodes.
        coordinator_weight = random()
        me = await get_my_org()

        # Store transaction state
        state = await self.get_state(transaction_hash)
        if not state:
            logger.error(f"Transaction {transaction_hash} not found in state")
            return
        state.coordinator_weights[me] = coordinator_weight
        state.peer_votes[me] = vote
        await self.set_state(transaction_hash, state)

        # Broadcast our vote to the other nodes
        logger.info(
            f"Broadcasting our vote and coordinator weight: {vote} (coord={coordinator_weight})"
        )
        await broadcast(
            data={
                "type": StarfishMessageType.PEER_SENT_OWN_VOTE,
                **StarfishMessagePeerSentOwnVote(
                    tx_hash=transaction_hash,
                    vote=vote,
                    coordinator_weight=coordinator_weight,
                ).model_dump(),
            },
            namespace=settings.namespace,
        )

    async def handle_event(self, event: EventCheckTransaction) -> None:
        """
        Handles EventCheckTransaction events by initializing the state in memory and firing the
        connector to verify the transaction.
        """
        # Get the current state of the transaction
        event_state = await self.get_state(event.ethTransactionHash)

        # If the transaction is already processing, ignore the event
        if event_state:
            return

        # Else, initialize the state machine
        await start_verification_job(
            VerifyTransactionIn(
                from_address=event.aliceEthAddress,
                to_address=event.mikeEthAddress,
                amount=event.ethAmount,
                transaction_hash=event.ethTransactionHash,
            )
        )
        state = CheckTransactionState(
            start_time=get_ntp_timestamp(),
            aliceEthAddress=event.aliceEthAddress,
            mikeEthAddress=event.mikeEthAddress,
            ethAmount=event.ethAmount,
            ethTransactionHash=event.ethTransactionHash,
        )
        await self.set_state(event.ethTransactionHash, state)

    async def handle_message(self, message: Message) -> None:
        # Parse message content
        content = self._parse_message_content(message)
        logger.info(
            f"Received message of type {content.__class__.__name__} from {message.from_org}: {content.model_dump()}"
        )

        # If a peer is asking for our Ethereum address, send it
        if isinstance(content, StarfishMessageAskForEthereumAddress):
            my_ethereum_address = await get_my_ethereum_address()
            message_to_send = StarfishMessageEthereumAddress(
                address=my_ethereum_address
            )
            logger.info(
                f"Sending my Ethereum address to {message.from_org}: {my_ethereum_address}"
            )
            await send_private_message(
                data={
                    "type": StarfishMessageType.ETHEREUM_ADDRESS,
                    **message_to_send.model_dump(),
                },
                to_org=message.from_org,
                namespace=settings.namespace,
            )
            return

        # If a peer is sending their Ethereum address, store it and, if we are the contract owner,
        # add the peer to LISTRACK's whitelist
        elif isinstance(content, StarfishMessageEthereumAddress):
            # Store peer's Ethereum address
            await self.set_peer_address(message.from_org, content.address)
            logger.info(
                f"Received Ethereum address from {message.from_org}: {content.address}"
            )
            # If we are the contract owner, add the peer to LISTRACK's whitelist
            my_ethereum_address = await get_my_ethereum_address()
            contract_owner_address = await get_contract_owner(
                namespace=settings.namespace
            )
            if my_ethereum_address == contract_owner_address:
                logger.info(f"Adding {message.from_org} to LISTRACK's whitelist")
                await add_peer_to_whitelist(content.address)
            return

        # If a peer has sent its own vote (along with its coordinator random number), we must
        # store it within the transaction state
        elif isinstance(content, StarfishMessagePeerSentOwnVote):
            # Get the current state of the transaction
            tx_state = await self.get_state(content.tx_hash)
            if not tx_state:
                logger.error(f"Received vote for unknown transaction {content.tx_hash}")
                return
            logger.info(
                f"Received vote from {message.from_org} (coord={content.coordinator_weight}): {content.vote}"
            )
            tx_state.coordinator_weights[message.from_org] = content.coordinator_weight
            tx_state.peer_votes[message.from_org] = content.vote
            await self.set_state(content.tx_hash, tx_state)
            return

        # If a peer has sent the computed result for the transaction, we must ensure that we
        # have the same understanding about who the coordinator is. If we do, we'll only store the
        # data if we are the coordinator. If we don't, we'll forward the message to the coordinator
        # we've elected.
        elif isinstance(content, StarfishMessagePeerSentComputedResult):
            # Get the current state of the transaction
            tx_state = await self.get_state(content.tx_hash)
            if not tx_state:
                logger.error(
                    f"Received result for unknown transaction {content.tx_hash}"
                )
                return
            logger.info(
                f"Received result from {message.from_org}: {content.model_dump()}"
            )

            # Check if we ourselves are the original sender of this message (avoid loops)
            my_org = await get_my_org()
            if content.originally_from == my_org:
                logger.info("Received message from ourselves, ignoring")
                return

            # Check if the number of hops for this message is greater than the maximum configured
            if content.hops > settings.message_forwarding_max_hops:
                logger.error(
                    f"Message has exceeded maximum hops ({content.hops}), ignoring"
                )
                return

            result = content.result
            coordinator = content.coordinator
            my_coordinator = tx_state.coordinator

            # If we don't have a coordinator yet, we must simply store the result
            if not my_coordinator:
                tx_state.results[message.from_org] = result
                await self.set_state(content.tx_hash, tx_state)
                logger.info(
                    f"Peer {message.from_org} has computed the result: {result}"
                )
                return

            # If our coordinator is different from the one in the message, forward it
            if my_coordinator != coordinator:
                logger.info(f"Forwarding result to {my_coordinator}")
                await send_private_message(
                    data={
                        "type": StarfishMessageType.PEER_SENT_COMPUTED_RESULT,
                        **content.model_dump(),
                        "hops": content.hops + 1,
                    },
                    to_org=my_coordinator,
                    namespace=settings.namespace,
                )
                return

            # If we agree on the coordinator and I'm not the coordinator, safely ignore the message
            if my_coordinator != my_org:
                logger.info("I'm not the coordinator, thus I'm ignoring the message")
                return

            # If we agree on the coordinator and I'm the coordinator, store the result
            tx_state.results[my_org] = tx_state.result
            tx_state.results[message.from_org] = result
            await self.set_state(content.tx_hash, tx_state)
            logger.info(f"Peer {message.from_org} has computed the result: {result}")

            return

        raise ValueError(f"Unsupported message type: {message.data.get('type')}")

    async def handle_states(self) -> None:
        """
        Continuously iterates over all transactions we're handling and take the appropriate actions.
        """
        # Get my org
        me = await get_my_org()

        # Iterate over all transactions in the state manager and handle them accordingly
        async for key in self._redis.scan_iter(match="tx:*"):
            transaction_hash = key.decode().split(":")[1]
            tx_state = await self.get_state(transaction_hash)
            # TODO (future): add some sort of mechanism to handle concurrency on tx state
            logger.info(
                f"I'm {me}. Handling state for transaction {transaction_hash}: {tx_state}"
            )

            # No state? Skip it
            if not tx_state:
                continue

            # Check if we have all votes for the transaction and still no result computed.
            # If so, compute the result and send it to the coordinator
            nodes_count = await get_nodes_count()
            if len(tx_state.peer_votes) == nodes_count and tx_state.result is None:
                logger.info("All votes received, computing result")

                # Choose the coordinator with the highest weight
                max_weight = max(tx_state.coordinator_weights.values())
                coordinator = [
                    k
                    for k, v in tx_state.coordinator_weights.items()
                    if v == max_weight
                ][0]
                logger.info(f"Coordinator elected: {coordinator}")

                # Choose result based on majority vote
                votes = list(tx_state.peer_votes.values())
                result = sum(votes) >= nodes_count / 2
                logger.info(f"Result computed: {result}")

                # Store the result in the transaction state
                tx_state.coordinator = coordinator
                tx_state.result = result
                await self.set_state(transaction_hash, tx_state)

                # Send our result to the coordinator
                logger.info(f"Sending computed result to {coordinator}")
                await send_private_message(
                    data={
                        "type": StarfishMessageType.PEER_SENT_COMPUTED_RESULT,
                        **StarfishMessagePeerSentComputedResult(
                            tx_hash=transaction_hash,
                            result=result,
                            coordinator=coordinator,
                            hops=0,
                            originally_from=me,
                        ).model_dump(),
                    },
                    to_org=coordinator,
                    namespace=settings.namespace,
                )

            # Check if we have all results received (if we're the coordinator). If so, send the
            # result back to the blockchain
            if tx_state.coordinator == me and len(tx_state.results) == nodes_count:
                logger.info("All results received, sending back to the blockchain")
                trade_id = await get_trade_id_by_transaction_hash(transaction_hash)
                await settle_trade(trade_id, tx_state.result)
                await self._redis.delete(key)
                # TODO: cleanup mechanism for peers that are not the coordinator

    async def handle_states_loop(self) -> None:
        while True:
            await self.handle_states()
            await asyncio.sleep(settings.state_manager_loop_interval)


state_manager = StateManager()
