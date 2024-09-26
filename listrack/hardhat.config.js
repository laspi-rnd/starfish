require("@nomicfoundation/hardhat-toolbox");
const fs = require("fs");
const path = require("path");

// Define the custom task
task("transfer-eth-to-members", "Transfers 10 ETH to each member's address from the stack.json")
  .setAction(async () => {
    const [sender] = await ethers.getSigners();
    const provider = ethers.getDefaultProvider();

    // Define the path to the stack.json file
    const jsonFilePath = path.join(process.env.HOME, ".firefly", "stacks", "hardhat", "stack.json");

    // Read and parse the JSON file
    let stackData;
    try {
      const jsonData = fs.readFileSync(jsonFilePath, 'utf8');
      stackData = JSON.parse(jsonData);
    } catch (error) {
      console.error("Error reading or parsing stack.json:", error);
      return;
    }

    // Check if members exist
    if (!stackData.members || stackData.members.length === 0) {
      console.error("No members found in stack.json");
      return;
    }

    console.log("Sending from:", sender.address);
    console.log("Account balance before transfer:", ethers.formatEther(await provider.getBalance(sender.address)), "ETH");

    // Iterate over members and transfer 10 ETH to each
    for (const member of stackData.members) {
      const walletAddress = member.account.address;

      if (!ethers.isAddress(walletAddress)) {
        console.error(`Invalid wallet address: ${walletAddress}`);
        continue;
      }

      try {
        // Convert 10 ETH to wei
        const amountInWei = ethers.parseEther("10");

        // Send the transaction
        const tx = await sender.sendTransaction({
          to: walletAddress,
          value: amountInWei,
        });

        console.log(`Transaction successful to ${walletAddress}. TX hash: ${tx.hash}`);
      } catch (error) {
        console.error(`Failed to send ETH to ${walletAddress}:`, error);
      }
    }

    console.log("Account balance after transfer:", ethers.formatEther(await provider.getBalance(sender.address)), "ETH");
  });

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.24",
  networks: {
    localhost: {
      chainId: 31337,
      url: "http://0.0.0.0:44950",
    },
  }
};
