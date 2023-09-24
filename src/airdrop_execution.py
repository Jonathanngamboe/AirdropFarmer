# airdrop_execution.py
import asyncio
import random
import traceback

from config import settings
from config.settings import BLOCKCHAIN_SETTINGS
from src.defi_handler import DeFiHandler
from src.twitter_handler import TwitterHandler
import os
import logging
import importlib.util

class AirdropExecution:
    def __init__(self, discord_handler=None, logger=None, wallets=None):
        self.logger = logger
        self.last_executed = {}  # Dictionary to store the last execution time
        self.airdrop_info = self.load_airdrop_files() # Load the airdrop files
        # Check if there is at least one Discord action
        self.has_discord_action = any(
            action["platform"] == "discord" for airdrop in self.airdrop_info for action in airdrop["actions"])
        self.discord_handler = discord_handler
        self.finished = False
        self.airdrops_to_execute = []
        self.airdrop_statuses = {}
        self.stop_requested = False
        self.wallets = wallets


    # Function to load airdrop files
    def load_airdrop_files(self):
        airdrops_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "airdrops"))
        airdrop_files = [f for f in os.listdir(airdrops_path) if f.endswith(".py")]

        airdrop_list = []
        for airdrop_file in airdrop_files:
            try:
                file_path = os.path.join(airdrops_path, airdrop_file)
                spec = importlib.util.spec_from_file_location(airdrop_file[:-3], file_path)
                airdrop_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(airdrop_module)
                airdrop_list.append(airdrop_module.airdrop_info)
            except Exception as e:
                self.logger.add_log(f"ERROR - Error loading {airdrop_file}: {e}", logging.ERROR)

        return airdrop_list

    # Function to get the active airdrops
    def get_active_airdrops(self):
        # Show the active airdrops
        active_airdrops = []
        for airdrop in self.airdrop_info:
            if airdrop["isActivated"]:
                active_airdrops.append(airdrop)
        return active_airdrops

    async def execute_single_airdrop(self, airdrop):
        message = "------------------------"
        self.logger.add_log(message)
        print(message)
        message = f"INFO - Executing actions for {airdrop['name']} airdrop"
        print(message)
        self.logger.add_log(message)

        success = await self.execute_airdrop_actions(airdrop)
        self.airdrop_statuses[airdrop['name']] = success

        # Message indicating that the actions for the current airdrop are finished
        message = f"INFO - Finished actions for {airdrop['name']} airdrop"
        print(message)
        self.logger.add_log(message)

    async def airdrop_execution(self):
        # Connect to Discord if there is at least one Discord action
        if self.has_discord_action:
            await self.discord_handler.connect()

        # Iterate through the airdrop files
        for airdrop in self.airdrop_info:
            if self.stop_requested:
                break
            if airdrop["isActivated"] and airdrop["name"] in self.airdrops_to_execute:
                await self.execute_single_airdrop(airdrop)
                # Wait for a random time if there are more airdrops to execute
                if airdrop != self.airdrop_info[-1]:
                    waiting_time = random.randint(settings.MIN_WAITING_SEC, settings.MAX_WAITING_SEC)
                    message = f"INFO - Waiting for {waiting_time} seconds before executing the next airdrop"
                    print(message)
                    self.logger.add_log(message)
                    await asyncio.sleep(waiting_time)

                # Yield control back to the event loop
                await asyncio.sleep(0)
            elif not self.airdrops_to_execute:
                message = f"INFO - No airdrop to execute"
                print(message)
                self.logger.add_log(message)

        self.finished = True

        return {airdrop: status for airdrop, status in zip(self.airdrops_to_execute, self.airdrop_statuses)}

    async def execute_airdrop_actions(self, airdrop_info):
        success = True  # Initialize success as True
        active_actions = [action for action in airdrop_info["actions"] if action["isActivated"]]
        # Shuffle the list
        #random.shuffle(active_actions)

        if not active_actions:
            message = f"INFO - No active actions found for {airdrop_info['name']} airdrop."
            print(message)
            self.logger.add_log(message)
            return

        for wallet in self.wallets:
            if self.stop_requested:  # Add this check
                break
            for action in active_actions:
                if self.stop_requested:  # Add this check
                    break
                message = "------------------------"
                print(message)
                self.logger.add_log(message)
                message = f"INFO - Executing action '{action['action'].replace('_', ' ')}' for {airdrop_info['name']} airdrop"
                print(message)
                self.logger.add_log(message)
                # Add the wallet's public address and private key to the action
                action["wallet"] = {"address": wallet["public_key"], "private_key": wallet["private_key"]}
                platform = action["platform"]

                try:
                    if platform == "twitter":
                        await TwitterHandler.perform_action(action)
                    elif platform == "discord":
                        await self.discord_handler.perform_action(action)
                    elif platform == "defi":
                        defi_handler = DeFiHandler(action["blockchain"], self.logger, self.stop_requested)
                        txn_hash = await defi_handler.perform_action(action)
                        if txn_hash is None:
                            message = f"ERROR - Due to an error while executing {platform} action for {airdrop_info['name']} airdrop, skipping this action."
                            success = False  # Set success to False if an error occurs
                        else:
                            message = f"INFO - Transaction hash : {BLOCKCHAIN_SETTINGS[action['blockchain']]['explorer_url']}{txn_hash}"
                    # If any exception occurs, log it and set success to False
                except Exception as e:
                    success = False
                    message = f"ERROR - An error occurred while executing action {platform} : {e}"
                    traceback.print_exc() # Uncomment this line to print the full stack trace
                print(message)
                self.logger.add_log(message)
                # Wait for a random time if there are more actions to execute
                if action != active_actions[-1]:
                    waiting_time = random.randint(settings.MIN_WAITING_SEC, settings.MAX_WAITING_SEC)
                    message = f"INFO - Waiting for {waiting_time} seconds before executing the next action"
                    print(message)
                    self.logger.add_log(message)
                    await asyncio.sleep(waiting_time)

        return success

    async def prepare_defi_transactions(self, user_id, db_manager, airdrop_names, public_key):
        self.logger.add_log("INFO - Preparing DeFi transactions")
        prepared_txns = []

        for airdrop_name in airdrop_names:
            airdrop = next((item for item in self.airdrop_info if item["name"] == airdrop_name), None)
            if airdrop is None:
                self.logger.add_log(f"ERROR - Airdrop {airdrop_name} not found")
                continue

            if airdrop['isActivated']:
                actions = airdrop['actions']
                for action in actions:
                    if action['platform'] == 'defi' and action['isActivated']:
                        defi_handler = DeFiHandler(action["blockchain"], self.logger, self.stop_requested)
                        prepared_tx = await defi_handler.prepare_transaction(action, public_key)
                        prepared_txns.append(prepared_tx)

        txn_key = await db_manager.insert_prepared_transaction(user_id, prepared_tx)

        return txn_key

