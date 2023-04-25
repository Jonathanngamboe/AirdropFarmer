# airdrop_execution.py
import asyncio
import time
from src.defi_handler import DeFiHandler
from src.twitter_handler import TwitterHandler
from config import settings
import os
import importlib.util

class AirdropExecution:
    def __init__(self, discord_handler, logger):
        self.last_executed = {}  # Dictionary to store the last execution time
        self.airdrop_info = self.load_airdrop_files() # Load the airdrop files
        # Check if there is at least one Discord action
        self.has_discord_action = any(
            action["platform"] == "discord" for airdrop in self.airdrop_info for action in airdrop["actions"])
        self.discord_handler = discord_handler
        self.logger = logger
        self.finished = False
        self.airdrops_to_execute = []
        self.airdrop_statuses = {}
        self.stop_requested = False


    # Function to load airdrop files
    def load_airdrop_files(self):
        airdrops_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "airdrops"))
        airdrop_files = [f for f in os.listdir(airdrops_path) if f.endswith(".py")]

        airdrop_list = []
        for airdrop_file in airdrop_files:
            file_path = os.path.join(airdrops_path, airdrop_file)
            spec = importlib.util.spec_from_file_location(airdrop_file[:-3], file_path)
            airdrop_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(airdrop_module)
            airdrop_list.append(airdrop_module.airdrop_info)

        return airdrop_list

    # Function to get the active airdrops
    def get_active_airdrops(self):
        return [airdrop for airdrop in self.airdrop_info if airdrop["isActivated"]]

    async def execute_airdrop_actions(self, airdrop_info):
        success = True  # Initialize success as True
        message = ""
        active_actions = [action for action in airdrop_info["actions"] if action["isActivated"]]

        if not active_actions:
            print(
                f"INFO - No active actions found for {airdrop_info['name']} airdrop.")
            return

        for wallet in settings.WALLET_LIST:
            if self.stop_requested:  # Add this check
                break
            for action in active_actions:
                if self.stop_requested:  # Add this check
                    break
                print("------------------------")
                # Add the wallet's public address and private key to the action
                action["wallet"] = {"address": wallet["address"], "private_key": wallet["private_key"]}
                platform = action["platform"]
                key = f"{airdrop_info['name']}_{platform}"
                now = time.time()

                # Check if there's a pending task on the same platform for the same airdrop
                is_pending_task = any(
                    k.startswith(airdrop_info["name"]) and k.endswith(platform) and
                    now - self.last_executed[k] < settings.PLATEFORM_WAIT_TIMES[platform]
                    for k in self.last_executed
                )

                if not is_pending_task:
                    try:
                        if platform == "twitter":
                            await TwitterHandler.perform_action(action)
                        elif platform == "discord":
                            await self.discord_handler.perform_action(action)
                        elif platform == "defi":
                            defi_handler = DeFiHandler(action["blockchain"])
                            txn_hash = defi_handler.perform_action(action)
                            if txn_hash is None:
                                message = f"ERROR - Error in executing action {platform} for {key} airdrop, skipping this action."
                                success = False  # Set success to False if an error occurs
                            else:
                                message = f"INFO - Transaction hash : {txn_hash}"
                        # If any exception occurs, log it and set success to False
                    except Exception as e:
                        success = False
                        message = f"ERROR - An error occurred while executing action {platform} : {e}"
                        # traceback.print_exc() # Uncomment this line to print the full stack trace
                    print(message)
                    self.logger.add_log(message)

                    self.last_executed[key] = now
                else:
                    print(
                        f"INFO - Skipping {platform} action for {airdrop_info['name']} due to delay constraint.")

        return success

    async def airdrop_execution(self):
        # Connect to Discord if there is at least one Discord action
        if self.has_discord_action:
            await self.discord_handler.connect()

        # Iterate through the airdrop files
        for airdrop in self.airdrop_info:
            if self.stop_requested:
                break
            if airdrop["isActivated"] and airdrop["name"] in self.airdrops_to_execute:
                print("------------------------")
                message = f"INFO - Executing actions for {airdrop['name']} airdrop"
                print(message)
                self.logger.add_log(message)

                success = await self.execute_airdrop_actions(airdrop)
                self.airdrop_statuses[airdrop['name']] = success

                # Message indicating that the actions for the current airdrop are finished
                message = f"INFO - Finished actions for {airdrop['name']} airdrop"
                print(message)
                self.logger.add_log(message)
            elif not self.airdrops_to_execute:
                message = f"INFO - No airdrop to execute"
                print(message)
                self.logger.add_log(message)

        self.finished = True

        return {airdrop: status for airdrop, status in zip(self.airdrops_to_execute, self.airdrop_statuses)}
