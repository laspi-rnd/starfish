// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract LISTRACK_ETH {
    // Event to emit when Alice submits her ETH transaction hash
    event CheckTransaction(
        address indexed aliceEthAddress,
        address indexed mikeEthAddress,
        uint256 ethAmount,
        string ethTransactionHash
    );

    // Event to emit when a trade is confirmed or canceled
    event TradeSettled(bytes32 indexed tradeId, bool confirmed);

    // Structure to hold trade details
    struct Trade {
        address aliceDrexAddress;
        address mikeDrexAddress;
        address aliceEthAddress;
        address mikeEthAddress;
        uint256 drexAmount;
        uint256 ethAmount;
        bool locked;
        bool settled;
    }

    // Contract owner (who can manage middleware nodes)
    address public owner;

    // Mapping to track the trades
    mapping(bytes32 => Trade) public trades;

    // Mapping to keep track of which transaction hash is associated with which trade
    mapping(string => bytes32) public tradeIdByTransactionHash;

    // Mapping to keep track of used alien transaction hashes
    mapping(bytes32 => bool) public usedAlienTx;

    // Mapping to store authorized middleware nodes
    mapping(address => bool) public middlewareNodes;

    // Modifier to restrict access to owner
    modifier onlyOwner() {
        require(
            msg.sender == owner,
            "Unauthorized: Only owner can perform this action"
        );
        _;
    }

    // Modifier to restrict access to authorized middleware nodes
    modifier onlyMiddleware() {
        require(
            middlewareNodes[msg.sender],
            "Unauthorized: Only middleware nodes can settle trades"
        );
        _;
    }

    constructor() {
        owner = msg.sender; // Set the contract deployer as the owner
    }

    // Function for Alice to set the trade details
    function setTrade(
        address _mikeDrexAddress,
        address _aliceEthAddress,
        address _mikeEthAddress,
        uint256 _drexAmount,
        uint256 _ethAmount,
        uint256 _nonce
    ) public returns (bytes32) {
        require(_drexAmount > 0, "Invalid DREX amount");
        require(_ethAmount > 0, "Invalid ETH amount");

        bytes32 tradeId = keccak256(
            abi.encodePacked(
                msg.sender,
                _mikeDrexAddress,
                _drexAmount,
                _ethAmount,
                _nonce
            )
        );

        require(
            trades[tradeId].aliceDrexAddress == address(0),
            "Trade already exists"
        );

        trades[tradeId] = Trade({
            aliceDrexAddress: msg.sender,
            mikeDrexAddress: _mikeDrexAddress,
            aliceEthAddress: _aliceEthAddress,
            mikeEthAddress: _mikeEthAddress,
            drexAmount: _drexAmount,
            ethAmount: _ethAmount,
            locked: false,
            settled: false
        });

        return tradeId;
    }

    function getTradeId(
        address _aliceDrexAddress,
        address _mikeDrexAddress,
        uint256 _drexAmount,
        uint256 _ethAmount,
        uint256 _nonce
    ) public pure returns (bytes32) {
        return
            keccak256(
                abi.encodePacked(
                    _aliceDrexAddress,
                    _mikeDrexAddress,
                    _drexAmount,
                    _ethAmount,
                    _nonce
                )
            );
    }

    function getTradeIdByTransactionHash(
        string memory _ethTransactionHash
    ) public view returns (bytes32) {
        return tradeIdByTransactionHash[_ethTransactionHash];
    }

    // Function for Mike to agree on Alice's terms and lock his DREX
    function agreeTrade(bytes32 tradeId) public payable {
        Trade storage trade = trades[tradeId];

        require(trade.aliceDrexAddress != address(0), "Trade does not exist");
        require(trade.mikeDrexAddress == msg.sender, "Unauthorized");
        require(!trade.locked, "Trade is already locked");
        require(msg.value == trade.drexAmount, "Incorrect DREX amount sent");

        trade.locked = true;
    }

    // Alice submits her ETH transaction hash
    function submitTransactionHash(
        bytes32 tradeId,
        string memory _ethTransactionHash
    ) public {
        Trade memory trade = trades[tradeId];

        require(trade.aliceDrexAddress != address(0), "Trade does not exist");
        require(trade.locked, "Trade is not locked");
        require(
            trade.aliceDrexAddress == msg.sender,
            "Only Alice can submit the transaction hash"
        );

        bytes32 txHash = keccak256(abi.encodePacked(_ethTransactionHash));
        require(!usedAlienTx[txHash], "Transaction hash already used");
        usedAlienTx[txHash] = true;
        tradeIdByTransactionHash[_ethTransactionHash] = tradeId;

        emit CheckTransaction(
            trade.aliceEthAddress,
            trade.mikeEthAddress,
            trade.ethAmount,
            _ethTransactionHash
        );
    }

    // Function to check the trade status by tradeId
    function getTradeStatus(
        bytes32 tradeId
    ) public view returns (Trade memory) {
        return trades[tradeId];
    }

    // Middleware-only function to confirm or cancel a trade
    function settleTrade(
        bytes32 tradeId,
        bool confirmed
    ) public onlyMiddleware {
        Trade storage trade = trades[tradeId];

        require(trade.aliceDrexAddress != address(0), "Trade does not exist");
        require(trade.locked, "Trade is not locked");
        require(!trade.settled, "Trade already settled");

        if (confirmed) {
            // Confirmed: Transfer DREX to Alice
            payable(trade.aliceDrexAddress).transfer(trade.drexAmount);
        } else {
            // Canceled: Refund DREX to Mike
            payable(trade.mikeDrexAddress).transfer(trade.drexAmount);
        }

        trade.settled = true; // Mark the trade as settled

        emit TradeSettled(tradeId, confirmed);
    }

    // Owner function to add a middleware node
    function addMiddlewareNode(address _middlewareNode) public onlyOwner {
        middlewareNodes[_middlewareNode] = true;
    }

    // Owner function to remove a middleware node
    function removeMiddlewareNode(address _middlewareNode) public onlyOwner {
        middlewareNodes[_middlewareNode] = false;
    }
}
