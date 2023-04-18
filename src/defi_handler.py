# defi_handler.py
from web3.exceptions import TimeExhausted, TransactionNotFound
from web3 import Web3
import requests
import json
from datetime import datetime
import time
import os
import config.settings as settings

class DeFiHandler:
    def __init__(self, blockchain):
        self.web3 = self.connect_to_blockchain(blockchain)

    def connect_to_blockchain(self, blockchain):
        if blockchain == 'ethereum':
            web3 = Web3(Web3.HTTPProvider(settings.ETHEREUM_MAINNET_ENDPOINT))
            self.token_abi = self.get_token_abi('erc20_abi.json')
        elif blockchain == 'goerli':
            web3 = Web3(Web3.HTTPProvider(settings.ETHEREUM_GOERLI_ENDPOINT))
            self.token_abi = self.get_token_abi('erc20_abi.json')
        elif blockchain == 'base_goerli':
            web3 = Web3(Web3.HTTPProvider(settings.BASE_GOERLI_ENDPOINT))
            self.token_abi = self.get_token_abi('erc20_abi.json')
        # Add more blockchains here if needed
        else:
            raise ValueError(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Unsupported blockchain.")
        if web3.isConnected():
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Successfully connected to {blockchain} blockchain.")
        else:
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Could not connect to {blockchain} blockchain.")
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Exiting program...")
            return None
        return web3

    def get_token_abi(self, filename):
        # Get the current file's directory
        current_directory = os.path.dirname(os.path.abspath(__file__))

        # Construct the path to the erc20_abi.json file
        token_abi_path = os.path.join(current_directory, '..', 'data', filename)

        # Read the token_abi.json file
        with open(token_abi_path, 'r') as f:
            token_abi = json.load(f)
        return token_abi

    def perform_action(self, action):
        if action["action"] == "interact_with_contract":
            # Convert address type arguments to checksum address
            function_args = self.convert_args_to_checksum_address(action["function_args"])
            return self.interact_with_contract(
                wallet = action["wallet"],
                contract_address=action["contract_address"],
                abi = action["abi"],
                function_name = action["function_name"],
                blockchain = action["blockchain"],
                msg_value = action["msg_value"] if "msg_value" in action else None,
                **function_args,
            )
        elif action["action"] == "transfer_native_token":
            return self.transfer_native_token(
                wallet = action["wallet"],
                amount_in_wei = int(action["amount_in_wei"]),
                recipient_address = self.web3.toChecksumAddress(action["recipient_address"].strip('"')),
                blockchain = action["blockchain"],
            )
        elif action["action"] == "transfer_token":
            return self.transfer_token(
                wallet = action["wallet"],
                token_address = self.web3.toChecksumAddress(action["token_address"].strip('"')),
                amount = int(action["amount"]),
                recipient_address = self.web3.toChecksumAddress(action["recipient_address"].strip('"')),
                blockchain = action["blockchain"],
            )
        elif action["action"] == "swap_tokens":
            return self.swap_tokens(
                wallet = action["wallet"],
                token_in_address = self.web3.toChecksumAddress(action["token_in_address"].strip('"')),
                token_out_address = self.web3.toChecksumAddress(action["token_out_address"].strip('"')),
                amount_in = int(action["amount_in"]),
                slippage_tolerance = action["slippage"],
                exchange_address = self.web3.toChecksumAddress(action["exchange_address"].strip('"')),
                exchange_abi = action["exchange_abi"],
                deadline_minutes = action["deadline_minutes"],
                blockchain = action["blockchain"]
            )

    def convert_args_to_checksum_address(self, args):
        converted_args = {}
        for key, arg in args.items():
            if isinstance(arg, str) and len(arg) == 42 and arg[:2] == "0x" and self.web3.isAddress(arg):
                # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Converting {arg} to checksum address.")
                converted_args[key] = self.web3.toChecksumAddress(arg.strip('"'))
            else:
                converted_args[key] = arg
        return converted_args

    def cancel_pending_transactions(self, blockchain, wallet):
        nonce = self.web3.eth.getTransactionCount(wallet["address"], 'pending')

        # Fetch recommended gas price
        gas_price = self.fetch_recommended_gas_price(blockchain)

        if gas_price is None:
            # Fallback to default gas price if fetching fails
            gas_price = self.web3.eth.gasPrice
        else:
            gas_price = int(gas_price * 1.5)

        gas_price = int(self.web3.toWei(gas_price, "gwei"))

        transaction = {
            'to': wallet["address"],
            'value': 0,
            'gas': 21000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': self.web3.eth.chainId
        }

        signed_txn = self.web3.eth.account.signTransaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash_hex = self.web3.toHex(txn_hash)
        return txn_hash_hex

    # Get the recommended Gas Price
    def fetch_recommended_gas_price(self, blockchain):
        try:
            if blockchain == 'ethereum':
                response = requests.get("https://api.etherscan.io/api?module=gastracker&action=gasoracle")
                gas_data = json.loads(response.text)
                gas_price = gas_data['result']['SafeGasPrice'] # Use 'ProposeGasPrice' or 'FastGasPrice' for faster transactions
            elif blockchain in ('goerli', 'base_goerli'):
                gas_price = self.web3.fromWei(self.web3.eth.gasPrice, 'gwei')
            gas_price = int(gas_price) if int(gas_price) > 0 else 1
            # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Recommended gas price : {gas_price} Gwei")
        except Exception as e:
            print(
                f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Error fetching gas price : {e}")
            gas_price = None
        return gas_price

    def gas_price_strategy(self, blockchain, transaction_params=None):
        gas_price = self.fetch_recommended_gas_price(blockchain)
        if gas_price is None:
            # Fallback to default gas price if fetching fails
            gas_price = self.web3.eth.gasPrice
        else:
            gas_price = int(gas_price * settings.GAS_PRICE_INCREASE)  # Increase the gas price by 20% to prioritize the transaction
        return gas_price

    def check_wallet_balance(self, wallet):
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Wallet {wallet['address']} balance : {self.web3.fromWei(self.web3.eth.getBalance(wallet['address']), 'ether')} ETH")
        return self.web3.eth.getBalance(wallet["address"])

    def get_token_name(self, token_address):
        # Create contract object
        token_contract = self.web3.eth.contract(address=Web3.toChecksumAddress(token_address), abi=self.token_abi)
        # Get the token name
        token_name = token_contract.functions.name().call()
        return token_name

    def build_and_send_transaction(self, wallet, function_call, blockchain, msg_value=None):
        # Estimate gas_price
        self.web3.eth.setGasPriceStrategy(
            lambda web3, transaction_params=None: self.gas_price_strategy(blockchain, transaction_params))
        gas_price = int(self.web3.toWei(self.web3.eth.generateGasPrice(), "gwei"))

        # Estimate gas_limit
        try:
            estimated_gas_limit = function_call.estimateGas({
                "from": wallet["address"],
                "value": msg_value if msg_value is not None else 0,
            })
        except ValueError as e:
            error_message = str(e)
            if "Insufficient msg.value" in error_message:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - {error_message}. Using default gas limit but transaction may fail.")
                estimated_gas_limit = 100000 # Set a default gas limit
            else:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Error estimating gas limit : {error_message}")
                return None
        # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Estimated gas limit : {estimated_gas_limit}")

        nonce = self.web3.eth.getTransactionCount(wallet["address"]) # Get the nonce for the wallet

        # Build the transaction
        transaction = function_call.buildTransaction({
            "chainId": self.web3.eth.chainId,
            "gas": estimated_gas_limit,
            "gasPrice": gas_price,
            "nonce": nonce,
            "value": msg_value if msg_value is not None else 0,
        })

        # Send the transaction and wait for it to be mined
        signed_txn = self.web3.eth.account.signTransaction(transaction, wallet["private_key"])
        try:
            txn_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        except ValueError as e:
            error_message = str(e)
            if "insufficient funds for gas * price + value" in error_message:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Insufficient funds for gas * price + value. Check your account balance.")
            else:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Unexpected error occurred while sending transaction: {error_message}")
            return
        txn_hash_hex = self.wait_for_transaction_mined(blockchain, wallet, txn_hash)

        return txn_hash_hex

    def wait_for_transaction_mined(self, blockchain, wallet, txn_hash, timeout=settings.DEFAULT_TRANSACTION_TIMEOUT):
        txn_hash_hex = self.web3.toHex(txn_hash)
        start_time = time.time()

        try:
            # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Waiting for transaction to be mined...")
            txn_receipt = self.web3.eth.waitForTransactionReceipt(txn_hash, timeout=timeout)

            if txn_receipt['status'] == 1:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Transaction succeeded.")
            else:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Transaction failed.")
                # Here, you can handle the failure and provide suggestions to the user
                # based on the error message, for example, if the message contains
                # "Transaction reverted".
        except TimeExhausted:
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Transaction has not been mined after the timeout. You may want to check the transaction manually : {txn_hash_hex}")
            return None
        except TransactionNotFound as e:
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Transaction not found: {txn_hash_hex}")
            return None
        except ValueError as e:
            error_message = str(e)
            if "replacement transaction underpriced" in error_message:
                print(
                    f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Replacement transaction underpriced. Canceling the previous transaction...")
                self.cancel_transaction(wallet, txn_hash)
            else:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Unexpected error occurred while waiting for transaction to be mined: {error_message}")
        except Exception as e:
            pending_txn = self.web3.eth.getTransaction(txn_hash)
            if pending_txn is not None:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Transaction taking too long to mine. Cancelling...")
                txn_hash_hex = self.cancel_pending_transactions(blockchain, wallet)
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Error waiting for transaction receipt:\n{e}")
        return txn_hash_hex

    def cancel_transaction(self, wallet, original_txn_hash):
        original_txn = self.web3.eth.getTransaction(original_txn_hash)
        nonce = original_txn["nonce"]
        gas_price = original_txn["gasPrice"]

        new_gas_price = int(gas_price * 1.1)  # Increase the gas price by 10%
        transaction = {
            "from": wallet["address"],
            "to": wallet["address"],
            "value": 0,
            "gas": 21000,
            "gasPrice": new_gas_price,
            "nonce": nonce,
            "chainId": self.web3.eth.chainId,
        }

        signed_txn = self.web3.eth.account.signTransaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash_hex = self.web3.toHex(txn_hash)

        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Cancelled original transaction. Sent a new transaction with hash {txn_hash_hex}")
        return txn_hash_hex

    def approve_token_spend(self, wallet, token_address, spender, amount, blockchain):
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Approving token spend...")
        contract = self.web3.eth.contract(
            address=token_address,
            abi=self.token_abi,
        )

        function_call = contract.functions.approve(spender, int(amount))

        return self.build_and_send_transaction(wallet, function_call, blockchain)

    def interact_with_contract(self, wallet, contract_address, abi, function_name, blockchain, msg_value=None, *args, **kwargs):
        contract = self.web3.eth.contract(address=contract_address, abi=abi)
        function = contract.functions[function_name]
        function_call = function(*args, **kwargs) # If gettting error "Function invocation failed due to no matching argument types", try to switch from *args to *kwargs or vice versa in the function call

        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Interacting with the function '{function_name}' of the contract {contract_address}")

        return self.build_and_send_transaction(wallet, function_call, blockchain, msg_value)

    def swap_tokens(self, wallet, token_in_address, token_out_address, amount_in, exchange_address, exchange_abi, blockchain, slippage_tolerance=0.1, deadline_minutes=3):
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Swapping {self.get_token_name(token_in_address)} for {self.get_token_name(token_out_address)} on contract {exchange_address}")

        # Approve contract to spend tokens if needed
        allowance = self.check_allowance(wallet, token_in_address, exchange_address)
        # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - The allowance is {self.web3.fromWei(allowance, 'ether')} and the amount to swap is {self.web3.fromWei(amount_in, 'ether')} {self.get_token_name(token_in_address)}.")
        if allowance < amount_in:
            approval_txn_hash = self.approve_token_spend(
                wallet,
                token_in_address,
                exchange_address,
                amount_in,
                blockchain,
            )
            if approval_txn_hash is None:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Token approval failed.")
                return
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Approval transaction hash: {approval_txn_hash}")
        else:
            # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Token allowance is sufficient.")
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

        txn_hash_hex = self.interact_with_contract(
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

    # This function is used to check the allowance of a spender for a token
    def check_allowance(self, wallet, token_address, spender):
        contract = self.web3.eth.contract(address=token_address, abi=self.token_abi)
        allowance = contract.functions.allowance(wallet["address"], spender).call()
        # print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Allowance for contract {spender} : {self.web3.fromWei(allowance, 'ether')} {self.get_token_name(token_address)}")
        return allowance

    def get_token_balance(self, wallet, token_address):
        """
        Get the balance of the specified token for the given wallet index.

        Args:
            wallet : A dict with the wallet public and private key.
            token_address (str): The address of the token contract.

        Returns:
            Decimal: The token balance of the wallet.
        """

        # Create a contract object for the token using its address and ABI
        token_contract = self.web3.eth.contract(address=Web3.toChecksumAddress(token_address), abi=self.token_abi)

        # Call the 'balanceOf' function of the token contract to get the balance
        token_balance = token_contract.functions.balanceOf(wallet["address"]).call()

        return token_balance

    def transfer_native_token(self, wallet, recipient_address, amount_in_wei, blockchain):
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Transfering {self.web3.fromWei(amount_in_wei, 'ether')} ETH from {wallet['address']} to {recipient_address}.")
        nonce = self.web3.eth.getTransactionCount(wallet["address"])

        # Estimate the gas required for the transaction
        gas_limit = self.web3.eth.estimateGas({
            'from': wallet["address"],
            'to': recipient_address,
            'value': amount_in_wei
        })

        transaction = {
            "from": wallet["address"],
            "to": recipient_address,
            "value": amount_in_wei,
            "gas": gas_limit,
            "gasPrice": self.web3.eth.gasPrice, # Set the gas price to the average network gas price
            "nonce": nonce,
            "chainId": self.web3.eth.chainId,
        }

        signed_txn = self.web3.eth.account.signTransaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash_hex = self.wait_for_transaction_mined(blockchain, wallet, txn_hash)

        return txn_hash_hex

    def transfer_token(self, wallet, recipient_address, amount, token_address, blockchain):
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Account balance before transfer: {self.web3.fromWei(self.get_token_balance(wallet, token_address), 'ether')} {self.get_token_name(token_address)}")
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Sending {self.web3.fromWei(amount, 'ether')} {self.get_token_name(token_address)} to {recipient_address}")
        contract = self.web3.eth.contract(address=token_address, abi=self.token_abi)
        function_call = contract.functions.transfer(recipient_address, amount)
        return self.build_and_send_transaction(wallet, function_call, blockchain)
