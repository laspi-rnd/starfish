# Variables
TEMP_NETWORK_PORT=44950
TEMP_NETWORK_IP=$(shell hostname -I | awk '{print $$1}')

.PHONY: hardhat start-firefly

# Rule to clean
clean:
	@echo "Removing FireFly stack..."
	ff stop hardhat && \
	ff remove hardhat -f

# Rule to start the HardHat node
start-network:
	@echo "Starting HardHat node on port $(TEMP_NETWORK_PORT)..."
	cd listrack && \
	npm install && \
	npx hardhat node --network hardhat --hostname 0.0.0.0 --port $(TEMP_NETWORK_PORT)

# Rule to generate the FireFly stack, transfer ETH, and start it
start-firefly:
	@echo "Generating FireFly stack..."
	cd listrack && \
	ff init hardhat 4 -p 8000 -v -n remote-rpc --chain-id 31337 --remote-node-url http://$(TEMP_NETWORK_IP):$(TEMP_NETWORK_PORT) --remote-node-deploy --connector-config evmconnect.yaml
	@echo "Transferring ETH to FireFly wallets..."
	cd listrack && \
	npx hardhat transfer-eth-to-members --network localhost
	@echo "Starting FireFly stack..."
	ff start hardhat
