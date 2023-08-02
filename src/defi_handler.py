# defi_handler.py
import asyncio
from web3.exceptions import TransactionNotFound
from web3 import Web3
import requests
import json
import time
import os
import config.settings as settings

# TODO: Implement feature to automatically vary activities across user wallets (e.g., token bridging on one, token swapping on another).
# TODO: Detect and alert users if they're synchronizing actions across multiple wallets (like simultaneous withdrawals or identical transactions).
# TODO: Wallet generation
class DeFiHandler:
    def __init__(self, blockchain, logger, stop_requested):
        self.logger = logger
        self.stop_requested = stop_requested
        self.web3 = self.connect_to_blockchain(blockchain)

    def connect_to_blockchain(self, blockchain):
        try:
            blockchain_settings = settings.BLOCKCHAIN_SETTINGS[blockchain]
        except KeyError:
            raise ValueError(f"Settings for blockchain '{blockchain}' not found.")
            return None

        endpoint = blockchain_settings['endpoint']
        web3 = Web3(Web3.HTTPProvider(endpoint))

        self.wrapped_native_token_address = blockchain_settings['weth_address']
        self.wrapped_native_token_abi = self.get_token_abi(blockchain_settings['weth_abi'])
        self.token_abi = self.get_token_abi(blockchain_settings['token_abi'])

        if web3.is_connected():
            message = f"INFO - Connected to {blockchain} blockchain."
            print(message)
            self.logger.add_log(message)
        else:
            message = f"INFO - Could not connect to {blockchain} blockchain."
            print(message)
            self.logger.add_log(message)
            message = f"INFO - Exiting program..."
            print(message)
            self.logger.add_log(message)
            return None
        return web3

    async def perform_action(self, action):
        # Print the wallet balance before start
        self.logger.add_log(f"INFO - Wallet : {action['wallet']['address']}\nINFO - Native token Balance : {self.get_token_balance(action['wallet'], native=True)}")
        # self.logger.add_log(f"INFO - Performing action : {action['description']}")

        # Replace placeholder with actual wallet address in action
        self.replace_placeholder_with_value(action, "<WALLET_ADDRESS>", action["wallet"]["address"])

        if action["action"] == "interact_with_contract":
            # Convert address type arguments to checksum address
            function_args = self.convert_args_to_checksum_address(action["function_args"])
            return await self.interact_with_contract(
                wallet = action["wallet"],
                contract_address=action["contract_address"],
                abi = action["abi"],
                function_name = action["function_name"],
                blockchain = action["blockchain"],
                msg_value = action["msg_value"] if "msg_value" in action else None,
                **function_args,
            )
        elif action["action"] == "transfer_native_token":
            return await self.transfer_native_token(
                wallet = action["wallet"],
                amount_in_wei = int(action["amount_in_wei"]),
                recipient_address = self.web3.to_checksum_address(action["recipient_address"].strip('"')),
                blockchain = action["blockchain"],
            )
        elif action["action"] == "transfer_token":
            return await self.transfer_token(
                wallet = action["wallet"],
                token_address = self.web3.to_checksum_address(action["token_address"].strip('"')),
                amount = int(action["amount"]),
                recipient_address = self.web3.to_checksum_address(action["recipient_address"].strip('"')),
            )
        elif action["action"] == "swap_native_token":
            return await self.swap_native_token(
                wallet = action["wallet"],
                amount = int(action["amount_in_wei"]),
                token_address = self.web3.to_checksum_address(action["token_address"].strip('"')),
                slippage_tolerance = action["slippage"],
                exchange_address = self.web3.to_checksum_address(action["exchange_address"].strip('"')),
                exchange_abi = action["exchange_abi"],
                deadline_minutes = action["deadline_minutes"],
                blockchain = action["blockchain"]
            )
        elif action["action"] == "swap_tokens":
            return await self.swap_tokens(
                wallet = action["wallet"],
                token_in_address = self.web3.to_checksum_address(action["token_in_address"].strip('"')),
                token_out_address = self.web3.to_checksum_address(action["token_out_address"].strip('"')),
                amount_in = int(action["amount_in_wei"]),
                slippage_tolerance = action["slippage"],
                exchange_address = self.web3.to_checksum_address(action["exchange_address"].strip('"')),
                exchange_abi = action["exchange_abi"],
                deadline_minutes = action["deadline_minutes"],
                blockchain = action["blockchain"]
            )

    def replace_placeholder_with_value(self, dictionary, placeholder, value):
        for key in dictionary:
            if isinstance(dictionary[key], dict):
                self.replace_placeholder_with_value(dictionary[key], placeholder, value)
            elif isinstance(dictionary[key], list):
                for item in dictionary[key]:
                    if isinstance(item, dict):
                        self.replace_placeholder_with_value(item, placeholder, value)
            elif dictionary[key] == placeholder:
                if value.startswith('0x') and len(value) == 42:  # Check if it's an EVM address
                    dictionary[key] = self.web3.to_checksum_address(value)  # Convert to checksum address
                else:
                    dictionary[key] = value

    def cancel_pending_transactions(self, blockchain, wallet):
        nonce = self.web3.eth.get_transaction_count(wallet["address"], 'pending')

        # Fetch recommended gas price
        gas_price = self.fetch_recommended_gas_price(blockchain)
        message = f"Recommended gas price: {gas_price} Gwei"
        print(message)
        self.logger.add_log(message)

        if gas_price is None:
            # Fallback to default gas price if fetching fails
            gas_price = self.web3.eth.gas_price
            message = f"Gas price is None, using default gas price: {gas_price} Gwei"
            print(message)
            self.logger.add_log(message)
        else:
            gas_price = int(gas_price * 1.5)

        gas_price = int(self.web3.to_wei(gas_price, "gwei"))
        message = f"Final gas price: {gas_price} wei"
        print(message)
        self.logger.add_log(message)

        transaction = {
            'to': wallet["address"],
            'value': 0,
            'gas': 21000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': self.web3.eth.chain_id
        }

        signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash_hex = self.web3.to_hex(txn_hash)
        return txn_hash_hex

    def get_token_abi(self, filename):
        # Get the current file's directory
        current_directory = os.path.dirname(os.path.abspath(__file__))

        # Construct the path to the erc20_abi.json file
        token_abi_path = os.path.join(current_directory, '..', 'resources', filename)

        # Read the token_abi.json file
        with open(token_abi_path, 'r') as f:
            token_abi = json.load(f)
        return token_abi

    def convert_args_to_checksum_address(self, args):
        converted_args = {}
        for key, arg in args.items():
            if isinstance(arg, str) and len(arg) == 42 and arg[:2] == "0x" and self.web3.is_address(arg):
                # print(f"INFO - Converting {arg} to checksum address.")
                converted_args[key] = self.web3.to_checksum_address(arg.strip('"'))
            else:
                converted_args[key] = arg
        return converted_args

    # Get the recommended Gas Price
    def fetch_recommended_gas_price(self, blockchain):
        try:
            if blockchain == 'ethereum':
                response = requests.get("https://api.etherscan.io/api?module=gastracker&action=gasoracle")
                gas_data = json.loads(response.text)
                gas_price = gas_data['result']['SafeGasPrice'] # Use 'ProposeGasPrice' or 'FastGasPrice' for faster transactions
            elif blockchain in ('goerli', 'base_goerli'):
                gas_price = self.web3.from_wei(self.web3.eth.gas_price, 'gwei')
            gas_price = int(gas_price) if int(gas_price) > 0 else 1
            # print(f"INFO - Recommended gas price : {gas_price} Gwei")
        except Exception as e:
            message = f"INFO - Error fetching gas price : {e}"
            print(message)
            self.logger.add_log(message)
            gas_price = None
        return gas_price

    def gas_price_strategy(self, blockchain):
        gas_price = self.fetch_recommended_gas_price(blockchain)
        if gas_price is None:
            # Fallback to default gas price if fetching fails
            gas_price = self.web3.eth.gas_price
        else:
            gas_price = int(gas_price * settings.GAS_PRICE_INCREASE)  # Increase the gas price by 20% to prioritize the transaction
        return gas_price

    def check_wallet_balance(self, wallet):
        message = f"INFO - Wallet {wallet['address']} balance : {self.web3.from_wei(self.web3.eth.get_balance(wallet['address']), 'ether')} ETH"
        print(message)
        self.logger.add_log(message)
        return self.web3.eth.get_balance(wallet["address"])

    def get_token_name(self, token_address):
        # Create contract object
        token_contract = self.web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=self.token_abi)
        # Get the token name
        token_name = token_contract.functions.name().call()
        return token_name

    async def build_and_send_transaction(self, wallet, function_call, msg_value=None):
        print(f"DEBUG - Building transaction for {wallet['address']}")
        gas_price = self.web3.eth.gas_price

        # Estimate gas_limit
        try:
            estimated_gas_limit = function_call.estimate_gas({
                "from": wallet["address"],
                "value": msg_value if msg_value is not None else 0,
            })
        except Exception as e:
            error_message = str(e)
            if "Insufficient msg.value" or "execution reverted: mvl" in error_message:
                message = f"ERROR - {error_message}. Using default gas limit but transaction may fail."
                print(message)
                self.logger.add_log(message)
                estimated_gas_limit = 100000 # Set a default gas limit
            else:
                message = f"ERROR - Error estimating gas limit : {error_message}"
                print(message)
                self.logger.add_log(message)
                return None
        # print(f"INFO - Estimated gas limit : {estimated_gas_limit}")

        nonce = self.web3.eth.get_transaction_count(wallet["address"], "pending")  # Get the nonce for the wallet, including pending transactions

        # Build the transaction
        transaction = function_call.build_transaction({
            "chainId": self.web3.eth.chain_id,
            "gas": estimated_gas_limit,
            "gasPrice": gas_price,
            "nonce": nonce,
            "value": msg_value if msg_value is not None else 0,
        })

        # Send the transaction and wait for it to be mined
        signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet["private_key"])
        try:
            txn_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        except ValueError as e:
            error_message = str(e)
            if "insufficient funds for gas * price + value" in error_message:
                message = f"ERROR - Insufficient funds for gas * price + value. Check your account balance."
                print(message)
                self.logger.add_log(message)
            else:
                message = f"ERROR - Unexpected error occurred while sending transaction: {error_message}"
                print(message)
                self.logger.add_log(message)
            return
        txn_hash_hex = await self.wait_for_transaction_mined(txn_hash)

        return txn_hash_hex

    async def wait_for_transaction_mined(self, txn_hash, timeout=settings.DEFAULT_TRANSACTION_TIMEOUT):
        txn_hash_hex = self.web3.to_hex(txn_hash)
        start_time = time.time()

        message = f"INFO - Waiting for transaction to be mined..."
        print(message)
        self.logger.add_log(message)
        txn_receipt = None
        while txn_receipt is None and time.time() - start_time < timeout:
            try:
                txn_receipt = self.web3.eth.get_transaction_receipt(txn_hash)
            except TransactionNotFound:
                await asyncio.sleep(1)
            except Exception as e:
                message = f"ERROR - Error while fetching transaction receipt : {e}"
                print(message)
                self.logger.add_log(message)
                return None
            if self.stop_requested:
                return None

        if txn_receipt is None:
            message = f"WARNING - Transaction has not been mined after the timeout. You may want to check the transaction manually : {txn_hash_hex}"
            print(message)
            self.logger.add_log(message)
            return None

        message = f"INFO - Transaction mined in {round(time.time() - start_time, 2)} seconds."
        print(message)
        self.logger.add_log(message)

        if txn_receipt['status'] == 1:
            message = f"INFO - Transaction succeeded."
            print(message)
            self.logger.add_log(message)
        else:
            message = f"INFO - Transaction failed."
            print(message)
            self.logger.add_log(message)

        return txn_hash_hex

    def cancel_transaction(self, wallet, original_txn_hash):
        original_txn = self.web3.eth.get_transaction(original_txn_hash)
        nonce = original_txn["nonce"]
        gas_price = original_txn["gasPrice"]

        new_gas_price = int(gas_price * 1.2)  # Increase the gas price by 20%
        transaction = {
            "from": wallet["address"],
            "to": wallet["address"],
            "value": 0,
            "gas": 21000,
            "gasPrice": new_gas_price,
            "nonce": nonce,
            "chainId": self.web3.eth.chain_id,
        }

        signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash_hex = self.web3.to_hex(txn_hash)

        message = f"INFO - Cancelled original transaction. Sent a new transaction with hash {txn_hash_hex}"
        print(message)
        self.logger.add_log(message)
        return txn_hash_hex

    def get_pending_transactions(self, wallet_address):
        pending_transactions = []

        # Get the transaction pool content
        try:
            txpool_content = self.web3.manager.request_blocking('txpool_content', [])
        except Exception as e:
            print("The connected node does not support 'txpool_content' method.")
            return pending_transactions

        # Check both queued and pending transactions
        for group in [txpool_content['queued'], txpool_content['pending']]:
            for txs in group.values():
                for tx in txs.values():
                    # Check if the transaction is related to the wallet_address
                    if tx['from'] == wallet_address:
                        pending_transactions.append(tx)

        print(f"Pending transactions : {pending_transactions}")

        return pending_transactions

    async def approve_token_spend(self, wallet, token_address, spender, amount, blockchain):
        message = f"INFO - Approving token spend..."
        print(message)
        self.logger.add_log(message)
        contract = self.web3.eth.contract(
            address=token_address,
            abi=self.token_abi,
        )

        function_call = contract.functions.approve(spender, int(amount))

        return await self.build_and_send_transaction(wallet, function_call)

    async def interact_with_contract(self, wallet, contract_address, abi, function_name, blockchain, msg_value=None, *args, **kwargs):
        contract = self.web3.eth.contract(address=contract_address, abi=abi)
        function = contract.functions[function_name]
        try:
            function_call = function(*args, **kwargs)
        except Exception as e:
            self.logger.add_log(f"ERROR - Error while building function call : {e}")
            # Print the kwargs
            self.logger.add_log(f"INFO - Arguments passed to the function :")
            self.logger.add_log(kwargs)
            print(f"ERROR - Error while building function call : {e}")
            return

        self.logger.add_log(f"INFO - Interacting with the function '{function_name}' of the contract {contract_address}")

        return await self.build_and_send_transaction(wallet, function_call, msg_value)

    async def swap_tokens(self, wallet, token_in_address, token_out_address, amount_in, exchange_address, exchange_abi, blockchain, slippage_tolerance=0.1, deadline_minutes=3):
        message = f"INFO - Swapping {self.get_token_name(token_in_address)} for {self.get_token_name(token_out_address)} on contract {exchange_address}"
        print(message)
        self.logger.add_log(message)

        # Check minimum transfer amount
        # Assuming `minimum_transfer_amount` function exists in the token contract
        contract = self.web3.eth.contract(address=token_in_address, abi=self.token_abi)
        try:
            min_transfer_amount = contract.functions.minimum_transfer_amount().call()
            if amount_in < min_transfer_amount:
                message = f"ERROR - Amount to swap is less than the minimum transfer amount."
                print(message)
                self.logger.add_log(message)
                return
            message = f"INFO - The minimum transfer amount is {self.web3.from_wei(min_transfer_amount, 'ether')} {self.get_token_name(token_in_address)}."
            print(message)
            self.logger.add_log(message)
        except Exception as e:
            # print(f"INFO - Token contract does not have a minimum_transfer_amount function.")
            pass

        # Check token balance
        token_balance = self.get_token_balance(wallet, token_in_address)
        message = f"INFO - The token balance is {self.web3.from_wei(token_balance, 'ether')} {self.get_token_name(token_in_address)}."
        print(message)
        self.logger.add_log(message)
        if token_balance < amount_in:
            message = f"ERROR - Insufficient token balance. Aborting..."
            print(message)
            self.logger.add_log(message)
            return

        # Approve contract to spend tokens if needed
        allowance = self.check_allowance(wallet, token_in_address, exchange_address)
        # print(f"INFO - The allowance is {self.web3.from_wei(allowance, 'ether')} and the amount to swap is {self.web3.from_wei(amount_in, 'ether')} {self.get_token_name(token_in_address)}.")
        if allowance < amount_in:
            approval_txn_hash = await self.approve_token_spend(
                wallet,
                token_in_address,
                exchange_address,
                amount_in,
                blockchain,
            )
            if approval_txn_hash is None:
                message = f"ERROR - Token approval failed."
                print(message)
                self.logger.add_log(message)
                return
            message = f"INFO - Approval transaction hash: {approval_txn_hash}"
            print(message)
            self.logger.add_log(message)
        else:
            # print(f"INFO - Token allowance is sufficient.")
            pass

        path = [token_in_address, token_out_address] # Path of tokens to swap

        # Calculate the min_amount_out by applying the slippage tolerance
        # Estimate the output amount by calling the `getAmountsOut` function
        contract = self.web3.eth.contract(address=exchange_address, abi=exchange_abi)
        amounts_out = contract.functions.getAmountsOut(amount_in, path).call()
        estimated_output_amount = amounts_out[-1]

        # Apply the slippage tolerance to the estimated_output_amount
        min_amount_out = max(0, int(estimated_output_amount * (1 - slippage_tolerance)))

        # Set the deadline to a specific number of minutes in the future
        deadline = int(time.time()) + (deadline_minutes * 60)

        txn_hash_hex = await self.interact_with_contract(
            wallet,
            exchange_address,
            exchange_abi,
            "swapExactTokensForTokens",
            blockchain,
            None,
            amount_in,
            min_amount_out,
            path,
            wallet["address"],
            deadline,
        )

        return txn_hash_hex

    async def swap_native_token(self, wallet, token_address, amount, exchange_address, exchange_abi,
                          blockchain, slippage_tolerance=0.1, deadline_minutes=3, is_buy=True):
        if is_buy:  # Swap native token for another token
            # Wrap native token
            wrap_txn_hash = await self.wrap_native_token(wallet, amount)
            if wrap_txn_hash is None:
                message = f"ERROR - Wrapping native token failed."
                print(message)
                self.logger.add_log(message)
                return
            message = f"INFO - Wrapping native token transaction hash: {wrap_txn_hash}"
            print(message)
            self.logger.add_log(message)

            # Perform swap
            swap_txn_hash = await self.swap_tokens(wallet, self.wrapped_native_token_address, token_address, amount, exchange_address,
                                             exchange_abi, blockchain, slippage_tolerance, deadline_minutes)
            return swap_txn_hash

        else:  # Swap another token for the native token
            # Perform swap
            swap_txn_hash = await self.swap_tokens(wallet, token_address, self.wrapped_native_token_address, amount, exchange_address,
                                             exchange_abi, blockchain, slippage_tolerance, deadline_minutes)
            return swap_txn_hash

    async def wrap_native_token(self, wallet, amount):
        message = f"INFO - Wrapping {self.web3.from_wei(amount, 'ether')} native tokens"
        print(message)
        self.logger.add_log(message)

        # Get the deposit function from the wrapped token contract
        contract = self.web3.eth.contract(address=self.wrapped_native_token_address, abi=self.wrapped_native_token_abi)
        deposit_function = contract.functions.deposit()

        # Estimate gas for the deposit function
        try:
            gas_estimate = deposit_function.estimate_gas({"from": wallet["address"], "value": amount})
        except Exception as e:
            message = f"ERROR - Error estimating gas limit: {str(e)}"
            print(message)
            self.logger.add_log(message)
            return None

        # Build and send the deposit transaction
        txn_hash_hex = await self.build_and_send_transaction(wallet, deposit_function, msg_value=amount)
        return txn_hash_hex

    # This function is used to check the allowance of a spender for a token
    def check_allowance(self, wallet, token_address, spender):
        contract = self.web3.eth.contract(address=token_address, abi=self.token_abi)
        allowance = contract.functions.allowance(wallet["address"], spender).call()
        # print(f"INFO - Allowance for contract {spender} : {self.web3.from_wei(allowance, 'ether')} {self.get_token_name(token_address)}")
        return allowance

    def get_token_balance(self, wallet, token_address=None, native=False):
        """
        Get the balance of the specified token or native token for the given wallet index.

        Args:
            wallet : A dict with the wallet public and private key.
            token_address (str, optional): The address of the token contract. Defaults to None.
            native (bool, optional): If True, return the native token balance. Defaults to False.

        Returns:
            Decimal: The token balance of the wallet.
        """

        if native:
            # Get the native token balance
            native_balance = self.web3.eth.get_balance(wallet["address"])
            return native_balance
        else:
            if token_address is None:
                raise ValueError("Token address is required if not fetching native token balance.")

            # Create a contract object for the token using its address and ABI
            token_contract = self.web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=self.token_abi)

            # Call the 'balanceOf' function of the token contract to get the balance
            token_balance = token_contract.functions.balanceOf(wallet["address"]).call()

            return token_balance

    async def transfer_native_token(self, wallet, recipient_address, amount_in_wei, blockchain):
        message = f"INFO - Transfering {self.web3.from_wei(amount_in_wei, 'ether')} ETH from wallet {wallet['address']} to {recipient_address}."
        print(message)
        self.logger.add_log(message)
        nonce = self.web3.eth.get_transaction_count(wallet["address"])

        try:
            # Estimate the gas required for the transaction
            gas_limit = self.web3.eth.estimate_gas({
                'from': wallet["address"],
                'to': recipient_address,
                'value': amount_in_wei
            })
        except Exception as e:
            message = f"ERROR - Error estimating gas limit : {e}"
            self.logger.add_log(message)
            print(message)
            return None

        transaction = {
            "from": wallet["address"],
            "to": recipient_address,
            "value": amount_in_wei,
            "gas": gas_limit,
            "gasPrice": self.web3.eth.gas_price, # Set the gas price to the average network gas price
            "nonce": nonce,
            "chainId": self.web3.eth.chain_id,
        }
        signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        message = f"Transaction hash in function 'transfer_native_token': {txn_hash.hex()}"
        print(message)
        self.logger.add_log(message)
        txn_hash_hex = await self.wait_for_transaction_mined(txn_hash)

        return txn_hash_hex

    async def transfer_token(self, wallet, recipient_address, amount, token_address):
        message = f"INFO - Account balance before transfer: {self.web3.from_wei(self.get_token_balance(wallet, token_address), 'ether')} {self.get_token_name(token_address)}"
        print(message)
        self.logger.add_log(message)
        message = f"INFO - Sending {self.web3.from_wei(amount, 'ether')} {self.get_token_name(token_address)} to {recipient_address}"
        print(message)
        self.logger.add_log(message)
        contract = self.web3.eth.contract(address=token_address, abi=self.token_abi)
        function_call = contract.functions.transfer(recipient_address, amount)
        return await self.build_and_send_transaction(wallet, function_call)