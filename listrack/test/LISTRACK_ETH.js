const { expect } = require("chai");
const { ethers } = require("hardhat");

// Function to generate trade ID in test code
function generateTradeId(_aliceDrexAddress, _mikeDrexAddress, _drexAmount, _ethAmount, _nonce) {
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const tradeId = ethers.keccak256(
      coder.encode(
          ["address", "address", "uint256", "uint256", "uint256"],
          [_aliceDrexAddress, _mikeDrexAddress, _drexAmount, _ethAmount, _nonce]
      )
  );
  return tradeId;
}

describe("LISTRACK_ETH Contract", function () {
  let LISTRACK, contract, owner, alice, mike, middleware1, middleware2;

  beforeEach(async function () {
    // Get signers
    [owner, alice, mike, middleware1, middleware2] = await ethers.getSigners();

    // Deploy contract
    LISTRACK = await ethers.getContractFactory("LISTRACK_ETH");
    contract = await LISTRACK.deploy();
  });

  describe("Middleware Management", function () {
    it("Should allow owner to add middleware nodes", async function () {
      await contract.addMiddlewareNode(middleware1.address);
      expect(await contract.middlewareNodes(middleware1.address)).to.be.true;
    });

    it("Should allow owner to remove middleware nodes", async function () {
      await contract.addMiddlewareNode(middleware1.address);
      await contract.removeMiddlewareNode(middleware1.address);
      expect(await contract.middlewareNodes(middleware1.address)).to.be.false;
    });

    it("Should prevent non-owner from adding/removing middleware nodes", async function () {
      await expect(contract.connect(alice).addMiddlewareNode(middleware1.address)).to.be.revertedWith("Unauthorized: Only owner can perform this action");
      await expect(contract.connect(alice).removeMiddlewareNode(middleware1.address)).to.be.revertedWith("Unauthorized: Only owner can perform this action");
    });
  });

  describe("Trade Creation and Agreement", function () {
    it("Should allow Alice to create a trade", async function () {
      await contract.connect(alice).setTrade(
        mike.address,    // Mike's DREX address
        alice.address,   // Alice's ETH address
        mike.address,    // Mike's ETH address
        ethers.parseEther("1.0"),  // 1 DREX
        ethers.parseEther("2.0"),  // 2 ETH
        1               // Nonce
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);
      const trade = await contract.getTradeStatus(tradeId);
      expect(trade.aliceDrexAddress).to.equal(alice.address);
    });

    it("Should allow Mike to agree and lock his DREX", async function () {
      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);
      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });
      const trade = await contract.getTradeStatus(tradeId);
      expect(trade.locked).to.be.true;
    });

    it("Should prevent Mike from agreeing with an incorrect DREX amount", async function () {
      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);
      await expect(
        contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("0.5") })
      ).to.be.revertedWith("Incorrect DREX amount sent");
    });
  });

  describe("Submit Transaction Hash", function () {
    it("Should allow Alice to submit the ETH transaction hash", async function () {
      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);

      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });

      const txHash = "0x123456789abcdef";
      // Check if the event is emitted
      await expect(contract.connect(alice).submitTransactionHash(tradeId, txHash))
        .to.emit(contract, "CheckTransaction")
        .withArgs(alice.address, mike.address, ethers.parseEther("2.0"), txHash);
    });

    it("Should prevent Alice from submitting the same ETH transaction hash", async function () {
      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);

      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });

      const txHash = "0x123456789abcdef";
      await contract.connect(alice).submitTransactionHash(tradeId, txHash);
      await expect(contract.connect(alice).submitTransactionHash(tradeId, txHash)).to.be.revertedWith("Transaction hash already used");
    });
  });

  describe("Trade Settlement by Middleware", function () {
    it("Should allow middleware node to confirm a trade", async function () {
      await contract.addMiddlewareNode(middleware1.address);

      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);

      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });

      await contract.connect(alice).submitTransactionHash(tradeId, "0xabcdef");
      
      await expect(contract.connect(middleware1).settleTrade(tradeId, true))
        .to.emit(contract, "TradeSettled")
        .withArgs(tradeId, true);
      
      const trade = await contract.getTradeStatus(tradeId);
      expect(trade.settled).to.be.true;
    });

    it("Should allow middleware node to cancel a trade", async function () {
      await contract.addMiddlewareNode(middleware1.address);

      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);

      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });

      await contract.connect(alice).submitTransactionHash(tradeId, "0xabcdef");

      await expect(contract.connect(middleware1).settleTrade(tradeId, false))
        .to.emit(contract, "TradeSettled")
        .withArgs(tradeId, false);
      
      const trade = await contract.getTradeStatus(tradeId);
      expect(trade.settled).to.be.true;
    });

    it("Should prevent re-settling a trade", async function () {
      await contract.addMiddlewareNode(middleware1.address);

      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);

      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });
      await contract.connect(alice).submitTransactionHash(tradeId, "0xabcdef");

      await contract.connect(middleware1).settleTrade(tradeId, true);
      
      await expect(contract.connect(middleware1).settleTrade(tradeId, true))
        .to.be.revertedWith("Trade already settled");
    });

    it("Should prevent unauthorized nodes from settling trades", async function () {
      await contract.connect(alice).setTrade(
        mike.address, 
        alice.address, 
        mike.address, 
        ethers.parseEther("1.0"), 
        ethers.parseEther("2.0"), 
        1
      );
      const tradeId = await contract.getTradeId(alice.address, mike.address, ethers.parseEther("1.0"), ethers.parseEther("2.0"), 1);

      await contract.connect(mike).agreeTrade(tradeId, { value: ethers.parseEther("1.0") });
      await contract.connect(alice).submitTransactionHash(tradeId, "0xabcdef");

      await expect(contract.connect(mike).settleTrade(tradeId, true))
        .to.be.revertedWith("Unauthorized: Only middleware nodes can settle trades");
    });
  });
});
