# defi_handler.py
import asyncio
import datetime
from statistics import median
from src.utils.file_utils import load_json
from web3.exceptions import TransactionNotFound
from web3 import Web3
import json
import time
import os
import config.settings as settings
from eth_account.messages import encode_structured_data
from decimal import Decimal
from eth_abi import encode
import httpx


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

        self.blockchain=blockchain
        self.wrapped_native_token_address = web3.to_checksum_address(blockchain_settings['weth_address'])
        self.wrapped_native_token_abi = self.get_token_abi(blockchain_settings['weth_abi'])
        self.token_abi = self.get_token_abi(blockchain_settings['token_abi'])

        if web3.is_connected():
            message = "------------------------\n"
            message += f"INFO - Connected to {blockchain} blockchain."
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
        message = f"INFO - Wallet: {action['wallet']['address']}\nINFO - Native token Balance: {self.web3.from_wei(self.get_token_balance(action['wallet'], native=True), 'ether')}\n------------------------"
        print(message)
        self.logger.add_log(message)

        # self.logger.add_log(f"INFO - Performing action: {action['description']}")

        # Replace placeholder with actual wallet address in action
        self.replace_placeholder_with_value(action, "<WALLET_ADDRESS>", action["wallet"]["address"])

        if action["action"] == "interact_with_contract":
            # Convert address type arguments to checksum address
            function_args = self.convert_args_to_checksum_address(action["function_args"])
            return await self.interact_with_contract(
                wallet=action["wallet"],
                contract_address=action["contract_address"],
                abi=action["abi"],
                function_name=action["function_name"],
                msg_value=action["msg_value"] if "msg_value" in action else None,
                **function_args,
            )
        elif action["action"] == "transfer_native_token":
            return await self.transfer_native_token(
                wallet=action["wallet"],
                amount_in_wei=int(action["amount_in_wei"]),
                recipient_address=self.web3.to_checksum_address(action["recipient_address"].strip('"')),
            )
        elif action["action"] == "transfer_token":
            return await self.transfer_token(
                wallet=action["wallet"],
                token_address=self.web3.to_checksum_address(action["token_address"].strip('"')),
                amount=int(action["amount"]),
                recipient_address=self.web3.to_checksum_address(action["recipient_address"].strip('"')),
            )
        elif action["action"] == "swap_native_token":
            return await self.swap_native_token(
                wallet=action["wallet"],
                amount=int(action["amount_in_wei"]),
                token_address=self.web3.to_checksum_address(action["token_address"].strip('"')),
                slippage_tolerance=action["slippage"],
                exchange_address=self.web3.to_checksum_address(action["exchange_address"].strip('"')),
                exchange_abi=action["exchange_abi"],
                deadline_minutes=action["deadline_minutes"],
                blockchain=action["blockchain"]
            )
        elif action["action"] == "swap_tokens":
            return await self.swap_tokens(
                wallet=action["wallet"],
                token_address=self.web3.to_checksum_address(action["token_address"].strip('"')),
                token_out_address=self.web3.to_checksum_address(action["token_out_address"].strip('"')),
                amount_in=int(action["amount_in_wei"]),
                slippage_tolerance=action["slippage"],
                exchange_address=self.web3.to_checksum_address(action["exchange_address"].strip('"')),
                exchange_abi=action["exchange_abi"],
                deadline_minutes=action["deadline_minutes"],
            )

        elif action["action"] == "swap_tokens_with_steps":
            return await self.swap_tokens_with_steps(
                wallet=action["wallet"],
                pool_address=self.web3.to_checksum_address(action["pool_address"].strip('"')),
                token_in=self.web3.to_checksum_address(action["token_in"].strip('"')) if action[
                                                                                             "token_in"] != "ETH" else
                action["token_in"],
                amount_in=int(action["amount_in"]),
                exchange_address=self.web3.to_checksum_address(action["exchange_address"].strip('"')),
                exchange_abi=action["exchange_abi"],
                deadline_minutes=action["deadline_minutes"] if "deadline_minutes" in action else 30,
            )
        elif action["action"] == "interact_with_api":
            return await self.interact_with_api(
                wallet=action["wallet"],
                quote_url=action["quote_url"],
                assemble_url=action["assemble_url"],
                method=action["api_method"] if "api_method" in action else "GET",
                params=action["api_params"] if "api_params" in action else None,
                data=action["api_data"] if "api_data" in action else None,
                headers=action["api_headers"] if "api_headers" in action else None,
                timeout=action["api_timeout"] if "api_timeout" in action else 10,
                json_payload=action["json_payload"] if "json_payload" in action else False,
            )
        elif action["action"] == "add_liquidity":
            return await self.add_liquidity(
                wallet=action["wallet"],
                router_address=self.web3.to_checksum_address(action["router_address"].strip('"')),
                router_abi=action["router_abi"],
                is_native=action["is_native"],
                token_a_address=self.web3.to_checksum_address(action["token_a_address"].strip('"')),
                amount_a_desired=int(action["amount_a_desired"]),
                amount_a_min=int(action["amount_a_min"]),
                amount_b_desired=int(action["amount_b_desired"]),
                token_b_address=self.web3.to_checksum_address(action["token_b_address"].strip('"')) if "token_b_address" in action else None,
                amount_b_min=int(action["amount_b_min"]) if "amount_b_min" in action else None,
                fee_type=action["fee_type"] if "fee_type" in action else 0,
                stable=action["stable"] if "stable" in action else False,
                deadline_minutes=int(action["deadline_minutes"]) if "deadline_minutes" in action else 30,
            )
        elif action["action"] == "remove_liquidity":
            return await self.remove_liquidity(
                wallet=action["wallet"],
                router_address=self.web3.to_checksum_address(action["router_address"].strip('"')),
                router_abi=action["router_abi"],
                is_native=action["is_native"],
                token_a_address=self.web3.to_checksum_address(action["token_a_address"].strip('"')),
                liquidity=int(action["liquidity"]),
                amount_a_min=int(action["amount_a_min"]),
                amount_b_desired=int(action["amount_b_desired"]),
                token_b_address=self.web3.to_checksum_address(action["token_b_address"].strip('"')) if "token_b_address" in action else None,
                amount_b_min=int(action["amount_b_min"]) if "amount_b_min" in action else None,
                stable=action["stable"] if "stable" in action else False,
                deadline_minutes=int(action["deadline_minutes"]) if "deadline_minutes" in action else 30,
            )

    def replace_placeholder_with_value(self, obj, placeholder, value):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list, tuple)):
                    obj[k] = self.replace_placeholder_with_value(v, placeholder, value)
                elif v == placeholder:
                    obj[k] = self.replace_value_with_appropriate_format(value)
        elif isinstance(obj, list):
            for i in range(len(obj)):
                if isinstance(obj[i], (dict, list, tuple)):
                    obj[i] = self.replace_placeholder_with_value(obj[i], placeholder, value)
                elif obj[i] == placeholder:
                    obj[i] = self.replace_value_with_appropriate_format(value)
        elif isinstance(obj, tuple):
            obj = list(obj)
            for i in range(len(obj)):
                if isinstance(obj[i], (dict, list, tuple)):
                    obj[i] = self.replace_placeholder_with_value(obj[i], placeholder, value)
                elif obj[i] == placeholder:
                    obj[i] = self.replace_value_with_appropriate_format(value)
            obj = tuple(obj)
        return obj

    def replace_value_with_appropriate_format(self, value):
        if str(value).startswith('0x'):
            if len(value) == 42:  # Check if it's an EVM address
                return self.web3.to_checksum_address(value)  # Convert to checksum address
            elif len(value) == 4 or len(value) == 66:  # Check if it's a signature component
                return value  # Replace with the signature component
        else:
            return value

    def cancel_pending_transactions(self, wallet):
        nonce = self.web3.eth.get_transaction_count(wallet["address"], 'pending')

        # Fetch recommended gas price
        gas_price = self.gas_price_strategy()

        message = f"INFO - Canceling pending transactions for {wallet['address']} with nonce {nonce} and gas price {gas_price}"
        print(message)
        self.logger.add_log(message)

        transaction = {
            'from': wallet["address"],
            'to': wallet["address"],
            'value': 0,
            'gas': int(self.web3.eth.estimate_gas({
                'from': wallet["address"],
                'to': wallet["address"],
                'value': 0,
            }) * 2),
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': self.web3.eth.chain_id
        }

        if wallet["private_key"] is None:
            return transaction

        signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet["private_key"])
        txn_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash_hex = self.web3.to_hex(txn_hash)

        message = f"INFO - Pending transactions canceled for {wallet['address']} with nonce {nonce} and gas price {gas_price} with hash {txn_hash_hex}"
        print(message)
        self.logger.add_log(message)

        return txn_hash_hex

    def get_token_abi(self, filename):
        # Get the current file's directory
        current_directory = os.path.dirname(os.path.abspath(__file__))

        # Construct the path to the erc20_abi.json file
        token_abi_path = os.path.join(current_directory, '..', 'resources', 'abis', filename)

        try:
            # Read the token_abi.json file
            with open(token_abi_path, 'r') as f:
                token_abi = json.load(f)
        except Exception as e:
            message = f"ERROR - Failed to read {token_abi_path} file"
            print(message)
            self.logger.add_log(message)
            raise e
        return token_abi

    def convert_to_checksum_address_recursive(self, item):
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, (dict, list, tuple, str)):
                    item[key] = self.convert_to_checksum_address_recursive(value)
        elif isinstance(item, list):
            for i, value in enumerate(item):
                item[i] = self.convert_to_checksum_address_recursive(value)
        elif isinstance(item, tuple):
            # Convert tuple to list, process it, then convert it back to tuple
            item = tuple(self.convert_to_checksum_address_recursive(list(item)))
        elif isinstance(item, str):
            if len(item) == 42 and item[:2] == "0x" and self.web3.is_address(item):
                return self.web3.to_checksum_address(item.strip('"'))
        return item

    def convert_args_to_checksum_address(self, args):
        return self.convert_to_checksum_address_recursive(args)

    def gas_price_strategy(self):
        return int(
            self.web3.eth.gas_price * settings.GAS_PRICE_INCREASE)  # Increase the gas price by 20% to prioritize the transaction

    def check_wallet_balance(self, wallet):
        message = f"INFO - Wallet {wallet['address']} balance: {self.web3.from_wei(self.web3.eth.get_balance(wallet['address']), 'ether')} ETH"
        print(message)
        self.logger.add_log(message)
        return self.web3.eth.get_balance(wallet["address"])

    def get_token_name(self, token_address):
        # Create contract object
        token_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(token_address),
                                                abi=self.token_abi)
        try:
            # Get the token name
            token_name = token_contract.functions.name().call()
            return token_name
        except Exception as e:
            message = f"ERROR - Error getting token name: {e}"
            print(message)
            self.logger.add_log(message)
            return "Unknown Token"

    async def build_and_send_transaction(self, wallet, function_call, msg_value=None):
        message = f"INFO - Building transaction for wallet {wallet['address']} with function call {function_call}"
        print(message)
        self.logger.add_log(message)

        gas_price = self.web3.eth.gas_price

        # Estimate gas_limit
        try:
            message = f"INFO - Estimating gas limit for wallet {wallet['address']}"
            print(message)
            self.logger.add_log(message)
            estimated_gas_limit = function_call.estimate_gas({
                "from": wallet["address"],
                "nonce": self.web3.eth.get_transaction_count(wallet["address"]),
                "value": msg_value if msg_value is not None else 0,
            })
        except Exception as e:
            error_message = str(e)
            if "Insufficient msg.value" in error_message or "execution reverted:" in error_message:
                message = f"ERROR - {error_message}."
                try:
                    estimated_gas_limit = int(
                        median(t.gas for t in self.web3.eth.get_block("latest", full_transactions=True).transactions))
                    message += "\nTrying to execute the transaction with last block average gas limit but it will probably fail."
                except Exception as e:
                    message += f"{e}"
                    return None
                finally:
                    print(message)
                    self.logger.add_log(message)
            else:
                message = f"ERROR - Error estimating gas limit: {error_message}"
                print(message)
                self.logger.add_log(message)
                return None
        message=f"INFO - Estimated gas limit: {estimated_gas_limit}"
        print(message)
        self.logger.add_log(message)

        nonce = self.web3.eth.get_transaction_count(wallet["address"])  # Get the nonce

        # Build the transaction
        transaction = function_call.build_transaction({
            "chainId": self.web3.eth.chain_id,
            "gas": estimated_gas_limit,
            "gasPrice": gas_price,
            "nonce": nonce,
            "value": msg_value if msg_value is not None else 0,
        })

        if wallet["private_key"] is None:
            return transaction

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
                message = f"ERROR - Error while fetching transaction receipt: {e}"
                print(message)
                self.logger.add_log(message)
                return None
            if self.stop_requested:
                return None

        if txn_receipt is None:
            message = f"WARNING - Transaction has not been mined after the timeout.\nYou may want to check the transaction manually: {settings.BLOCKCHAIN_SETTINGS[self.blockchain]['explorer_url']}{txn_hash_hex}"
            print(message)
            self.logger.add_log(message)
            return None

        message = f"INFO - Transaction mined in {round(time.time() - start_time, 2)} seconds with status: "

        if txn_receipt['status'] == 1:
            message += "Success!"
        elif txn_receipt['status'] == None:
            message += f"None. You may want to check the transaction manually: {settings.BLOCKCHAIN_SETTINGS[self.blockchain]['explorer_url']}{txn_hash_hex}"
        else:
            message += "Failed."

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

        if wallet["private_key"] is None:
            return transaction

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

        print(f"Pending transactions: {pending_transactions}")

        return pending_transactions

    async def approve_token_spend(self, wallet, token_address, spender, amount):
        message = f"INFO - Approving contract {token_address} to spend {amount} {self.get_token_name(token_address)}..."
        print(message)
        self.logger.add_log(message)
        contract = self.web3.eth.contract(
            address=token_address,
            abi=self.token_abi,
        )

        function_call = contract.functions.approve(spender, int(amount))

        return await self.build_and_send_transaction(wallet, function_call)

    async def ensure_token_approval(self, wallet, token_address, spender, amount):
        allowance = await self.check_allowance(wallet, token_address, spender)
        if allowance < amount:
            message = f"INFO - The actual allowance is {allowance} {self.get_token_name(token_address)} and the desired amount is {amount} {self.get_token_name(token_address)}."
            self.logger.add_log(message)
            print(message)
            # If allowance is already set but not enough, first reset it to zero (some tokens require this)
            if allowance > 0:
                message = f"INFO - Resetting allowance to zero before setting the desired amount..."
                self.logger.add_log(message)
                print(message)
                await self.approve_token_spend(wallet, token_address, spender, 0)

            # Approve the desired amount
            await self.approve_token_spend(wallet, token_address, spender, amount)

    async def interact_with_contract(self, wallet, contract_address, abi, function_name, msg_value=None, *args,
                                     **kwargs):
        contract = self.web3.eth.contract(address=contract_address, abi=abi)
        function = contract.functions[function_name]
        try:
            function_call = function(*args, **kwargs)
        except Exception as e:
            self.logger.add_log(f"ERROR - Error while building function call: {e}")
            print(f"ERROR - Error while building function call: {e}")
            # Show all the arguments passed and their types
            if args:
                print(
                    f"INFO - Positional arguments passed to the function '{function_name}' of the contract {contract_address}:")
                for arg in args:
                    print(f"INFO - {arg} ({type(arg)})")
            if kwargs:
                print(
                    f"INFO - Keyword arguments passed to the function '{function_name}' of the contract {contract_address}:")
                for key, value in kwargs.items():
                    print(f"INFO - {key} = {value} ({type(value)})")

            return

        self.logger.add_log(
            f"INFO - Interacting with the function '{function_name}' of the contract {contract_address}")

        return await self.build_and_send_transaction(wallet, function_call, msg_value)

    async def swap_tokens(self, wallet, token_in_address, token_out_address, amount_in, exchange_address, exchange_abi,
                          slippage_tolerance=0.1, deadline_minutes=3):
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
        allowance = await self.check_allowance(wallet, token_in_address, exchange_address)
        # print(f"INFO - The allowance is {self.web3.from_wei(allowance, 'ether')} and the amount to swap is {self.web3.from_wei(amount_in, 'ether')} {self.get_token_name(token_in_address)}.")
        if allowance < amount_in:
            approval_txn_hash = await self.approve_token_spend(
                wallet,
                token_in_address,
                exchange_address,
                amount_in,
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

        path = [token_in_address, token_out_address]  # Path of tokens to swap

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
            swap_txn_hash = await self.swap_tokens(wallet, self.wrapped_native_token_address, token_address, amount,
                                                   exchange_address, exchange_abi, slippage_tolerance, deadline_minutes)
            return swap_txn_hash

        else:  # Swap another token for the native token
            # Perform swap
            swap_txn_hash = await self.swap_tokens(wallet, token_address, self.wrapped_native_token_address, amount,
                                                   exchange_address, exchange_abi, slippage_tolerance, deadline_minutes)
            return swap_txn_hash

    async def swap_tokens_with_steps(self, wallet, pool_address, token_in, amount_in,
                                     exchange_address, exchange_abi, deadline_minutes=30):
        """
        Swap tokens with steps
        :param wallet:
        :param pool_address:
        :param token_in:
        :param amount_in:
        :param exchange_address:
        :param exchange_abi:
        :param deadline_minutes:
        :return: Transaction hash
        """

        if token_in == 'ETH':
            token_in_address = '0x' + '0' * 40
            actual_token_in = self.wrapped_native_token_address
        else:
            token_in_address = self.web3.to_checksum_address(token_in)
            actual_token_in = self.web3.to_checksum_address(token_in)

        message = "INFO - Swap in progress..."
        print(message)
        self.logger.add_log(message)

        # Ensure token is approved
        await self.ensure_token_approval(wallet, actual_token_in, exchange_address, amount_in)

        withdraw_mode = 1

        swap_data = encode(
            ['address', 'address', 'uint8'],
            [self.web3.to_checksum_address(actual_token_in), self.web3.to_checksum_address(wallet["address"]),
             withdraw_mode]
        )

        steps = [{
            'pool': self.web3.to_checksum_address(pool_address),
            'data': swap_data,
            'callback': self.web3.to_checksum_address('0x0000000000000000000000000000000000000000'),
            'callbackData': '0x',
        }]

        paths = [{
            'steps': steps,
            'tokenIn': self.web3.to_checksum_address(token_in_address),
            'amountIn': int(amount_in),
        }]

        # Set the deadline to a specific number of minutes in the future
        deadline_timestamp = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=deadline_minutes)).timestamp())

        # Get the router contract
        router = self.web3.eth.contract(address=exchange_address, abi=exchange_abi)

        try:
            # Construct the transaction
            transaction = router.functions.swap(
                paths,
                0,  # amountOutMin (not used) NOTE: Ensure slippage here
                deadline_timestamp
            ).build_transaction({
                'chainId': self.web3.eth.chain_id,
                'from': self.web3.to_checksum_address(wallet['address']),
                'maxFeePerGas': self.web3.eth.gas_price * 2,
                'maxPriorityFeePerGas': self.web3.eth.gas_price,
                'gas': 1500000,  # int(self.web3.eth.estimate_gas({
                # 'from': self.web3.to_checksum_address(wallet['address']),
                # 'to': self.web3.to_checksum_address(exchange_address),
                # 'value': amount_in if token_in == 'ETH' else 0,
                # }) * 2),
                'nonce': self.web3.eth.get_transaction_count(wallet['address'], 'latest'),
                'value': amount_in if token_in == 'ETH' else 0,
            })

            if wallet["private_key"] is None:
                return transaction

            try:
                # Signs and sends the transaction.
                signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet['private_key'])
                txn_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                txn_hash_hex = await self.wait_for_transaction_mined(txn_hash)
            except Exception as e:
                raise Exception(f"ERROR - An error occurred while sending the transaction: {e}")
            return txn_hash_hex

        except Exception as e:
            raise Exception(f"ERROR - An error occurred while processing the swap: {e}")

    async def _send_api_request(self, url, method="GET", params=None, data=None, headers=None, timeout=10, json=None):
        """
        Interact with an API.

        Args:
        - url (str): The endpoint URL.
        - method (str): HTTP method (e.g., "GET", "POST", "PUT", "DELETE").
        - params (dict): URL parameters.
        - data (dict): Data payload for POST, PUT, etc.
        - headers (dict): Headers for the request.
        - timeout (int): Timeout for the request in seconds.
        - json_payload (dict): JSON payload for the request.

        Returns:
        - Response object.
        """
        if method not in ["GET", "POST", "PUT", "DELETE"]:
            raise ValueError("Unsupported HTTP method.")

        response = None
        request = None  # Initialize the request object outside the context manager
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    request = client.build_request("GET", url, params=params, headers=headers)
                    response = await client.send(request)
                elif method == "POST":
                    request = client.build_request("POST", url, json=json if json else data, headers=headers)
                    response = await client.send(request)
                elif method == "PUT":
                    request = client.build_request("PUT", url, json=json if json else data, headers=headers)
                    response = await client.send(request)
                elif method == "DELETE":
                    request = client.build_request("DELETE", url, headers=headers)
                    response = await client.send(request)

                if 200 <= response.status_code < 300:
                    return response
                else:
                    raise httpx.HTTPStatusError(
                        f"HTTP ERROR: {response.status_code} - {response.text}",
                        request=request,  # Pass the request object
                        response=response)  # Pass the response object
        except httpx.HTTPStatusError as e:
            message = f"ERROR - {e}"
            print(message)
            self.logger.add_log(message)
            if response and hasattr(response, "status_code"):
                message = f"Error response headers: {response.headers}\n"
                message += f"Error response content: {response.text}\n"
                print(message)
                self.logger.add_log(message)
            return None

    async def interact_with_api(self, wallet, quote_url, assemble_url, method="GET", params=None, data=None, headers=None, timeout=10,
                                json_payload=None):
        ###########################################
        # Step 1: Generate a Quote
        ###########################################

        response_quote = await self._send_api_request(quote_url, method, params, data, headers, timeout, json_payload)
        if not response_quote:
            message = f"ERROR - An error occurred while generating a quote"
            print(message)
            self.logger.add_log(message)
            return None
        quote = response_quote.json()

        ###########################################
        # Step 2: Assemble the Transaction
        ###########################################

        assemble_request_body = {
            "userAddr": self.web3.to_checksum_address(wallet["address"]),
            "pathId": quote["pathId"],
            "simulate": False,
        }

        response_assemble = await self._send_api_request(assemble_url, "POST", headers={"Content-Type": "application/json"},
                                                         json=assemble_request_body
                                                         )

        if not response_assemble:
            message = f"ERROR - An error occurred while assembling the transaction"
            print(message)
            self.logger.add_log(message)
            return None
        assembled_transaction = response_assemble.json()

        ###########################################
        # Step 3: Execute the Transaction
        ###########################################

        # Extract transaction object from assemble API response
        transaction = assembled_transaction["transaction"]
        # add the chainId to the transaction object from the API if signing raw transaction
        transaction["chainId"] = json_payload["chainId"]
        # web3 requires the value to be an integer
        transaction["value"] = int(transaction["value"])
        # web3 requires checksummed addresses
        transaction["from"] = self.web3.to_checksum_address(transaction["from"])
        transaction["to"] = self.web3.to_checksum_address(transaction["to"])

        if wallet["private_key"] is None:
            return transaction

        try:
            # Sign the transaction
            signed_tx = self.web3.eth.account.sign_transaction(transaction, wallet["private_key"])
            # Send the signed transaction
            txn_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            txn_hash_hex = await self.wait_for_transaction_mined(txn_hash)
        except Exception as e:
            raise Exception(f"ERROR - An error occurred while processing the swap: {e}")

        return txn_hash_hex

    async def wrap_native_token(self, wallet, amount):
        message = f"INFO - Wrapping {self.web3.from_wei(amount, 'ether')} native tokens"
        print(message)
        self.logger.add_log(message)

        # Get the deposit function from the wrapped token contract
        contract = self.web3.eth.contract(address=self.wrapped_native_token_address, abi=self.wrapped_native_token_abi)
        deposit_function = contract.functions.deposit()

        # Build and send the deposit transaction
        txn_hash_hex = await self.build_and_send_transaction(wallet, deposit_function, msg_value=amount)
        return txn_hash_hex

    # This function is used to check the allowance of a spender for a token
    async def check_allowance(self, wallet, token_address, spender):
        contract = self.web3.eth.contract(address=token_address, abi=self.token_abi)
        message = f"INFO - Checking allowance for contract {spender}..."
        print(message)
        self.logger.add_log(message)
        allowance = contract.functions.allowance(wallet["address"], spender).call()
        if token_address == self.wrapped_native_token_address:
            message = f"INFO - Allowance for contract {spender}: {self.web3.from_wei(allowance, 'ether')} {self.get_token_name(token_address)}"
        else:
            message = f"INFO - Allowance for contract {spender}: {allowance} {self.get_token_name(token_address)}"
        print(message)
        self.logger.add_log(message)
        return allowance

    def get_token_balance(self, wallet, token_address=None, native=False):
        """
        Get the balance of the specified token or native token for the given wallet index.

        Args:
            wallet: A dict with the wallet public and private key.
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

    async def transfer_native_token(self, wallet, recipient_address, amount_in_wei):
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
            message = f"ERROR - Error estimating gas limit: {e}"
            self.logger.add_log(message)
            print(message)
            return None

        transaction = {
            "from": wallet["address"],
            "to": recipient_address,
            "value": amount_in_wei,
            "gas": gas_limit,
            "gasPrice": self.web3.eth.gas_price,  # Set the gas price to the average network gas price
            "nonce": nonce,
            "chainId": self.web3.eth.chain_id,
        }

        if wallet["private_key"] is None:
            return transaction

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

    async def read_and_replace_message(self, filepath, replacements):
        message = load_json(filepath)

        for placeholder, value in replacements.items():
            self.replace_placeholder_with_value(message, placeholder, value)

        return message

    async def sign_message(self, wallet, message):
        """
        Sign a message with a wallet's private key
        :param wallet: The wallet used to sign the message
        :param message: The message to sign
        :return: signature object with v, r, and s components
        """
        msg = encode_structured_data(text=json.dumps(message))
        signed_message = self.web3.eth.account.sign_message(msg, private_key=wallet["private_key"])
        return signed_message

    async def add_liquidity(self, wallet, router_address, router_abi, token_a_address, amount_a_desired, amount_a_min,
                            amount_b_desired, deadline_minutes, is_native, token_b_address=None, amount_b_min=None, fee_type=None, stable=None):
        message = f"INFO - Adding liquidity for {self.get_token_name(token_a_address)}..."
        print(message)
        self.logger.add_log(message)

        # Approve the router to spend the tokens
        await self.ensure_token_approval(wallet, token_a_address, router_address, amount_a_desired)

        # Calculate the deadline timestamp
        deadline_timestamp = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=deadline_minutes)).timestamp())

        contract = self.web3.eth.contract(address=router_address, abi=router_abi)

        if is_native:
            function_call = contract.functions.addLiquidityETH(
                token=token_a_address,
                amountTokenDesired=amount_a_desired,
                amountTokenMin=amount_a_min,
                amountETHMin=amount_b_desired,
                to=wallet["address"],
                deadline=deadline_timestamp,
                feeType=fee_type,
                stable=stable
            )
        else:
            # Approve the router to spend the tokens
            await self.ensure_token_approval(wallet, token_b_address, router_address, amount_b_desired)
            function_call = contract.functions.addLiquidity(
                tokenA=token_a_address,
                tokenB=token_b_address,
                amountADesired=amount_a_desired,
                amountBDesired=amount_b_desired,
                amountAMin=amount_a_min,
                amountBMin=amount_b_min,
                to=wallet["address"],
                deadline=deadline_timestamp,
                feeType=fee_type,
                stable=stable
            )

        return await self.build_and_send_transaction(wallet, function_call, msg_value=int(1.5*amount_b_desired) if is_native else 0)

    async def remove_liquidity(self, wallet, router_address, router_abi, token_a_address, liquidity, amount_a_min,
                            amount_b_desired, deadline_minutes, is_native, token_b_address=None, amount_b_min=None, stable=None):
        message = f"INFO - Removing liquidity for {self.get_token_name(token_a_address)}..."
        print(message)
        self.logger.add_log(message)

        # Calculate the deadline timestamp
        deadline_timestamp = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=deadline_minutes)).timestamp())

        contract = self.web3.eth.contract(address=router_address, abi=router_abi)

        # Approve the router to spend the tokens
        await self.ensure_token_approval(wallet, token_a_address, router_address, liquidity)

        if is_native:
            function_call = contract.functions.removeLiquidityETHSupportingFeeOnTransferTokens(
                token=token_a_address,
                liquidity=liquidity,
                amountTokenMin=amount_a_min,
                amountETHMin=amount_b_desired,
                to=wallet["address"],
                deadline=deadline_timestamp,
                stable=stable
            )
        else:
            # Approve the router to spend the tokens
            await self.ensure_token_approval(wallet, token_b_address, router_address, amount_b_min)
            function_call = contract.functions.removeLiquidity(
                tokenA=token_a_address,
                tokenB=token_b_address,
                liquidity=liquidity,
                amountAMin=amount_a_min,
                amountBMin=amount_b_min,
                to=wallet["address"],
                deadline=deadline_timestamp,
                stable=stable
            )

        return await self.build_and_send_transaction(wallet, function_call, msg_value=0)

    async def prepare_transaction(self, action, public_key):
        action["wallet"] = {"address": public_key, "private_key": None}
        return await self.perform_action(action)