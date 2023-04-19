import time
from datetime import datetime
import asyncio
import discord
import traceback
import os
import importlib.util
from src.twitter_handler import TwitterHandler
from src.discord_handler import DiscordHandler
from src.defi_handler import DeFiHandler
from src.telegram_bot import register_handlers
from aiogram import Dispatcher, Bot
import config.settings as settings

class AirdropFarmer:
    def __init__(self):
        self.connected_to_discord_event = asyncio.Event()
        self.discord_handler = DiscordHandler(self.connected_to_discord_event)
        self.last_executed = {}  # Dictionary to store the last execution time

    async def initialize(self):
        message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Welcome to the Airdrop Farming Bot!"
        print(message)

    async def execute_airdrop_actions(self, airdrop_info):
        active_actions = [action for action in airdrop_info["actions"] if action["isActivated"]]

        if not active_actions:
            print(
                f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - No active actions found for {airdrop_info['name']} airdrop.")
            return

        for wallet in settings.WALLET_LIST:
            for action in active_actions:
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

                if key not in self.last_executed or now - self.last_executed[key] >= settings.PLATEFORM_WAIT_TIMES[
                    platform]:
                    if platform == "twitter":
                        await TwitterHandler.perform_action(action)
                    elif platform == "discord":
                        await self.discord_handler.perform_action(action)
                    elif platform == "defi":
                        defi_handler = DeFiHandler(action["blockchain"])
                        try:
                            txn_hash = defi_handler.perform_action(action)
                            if txn_hash is None:
                                message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Error in executing action {platform} for {key} airdrop, skipping this action."
                            else:
                                message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Transaction hash : {txn_hash}"
                        except Exception as e:
                            message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - An error occurred while executing action {platform} : {e}"
                            # traceback.print_exc() # Uncomment this line to print the full stack trace
                        print(message)

                    self.last_executed[key] = now
                    print(
                        f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Waiting for {settings.PLATEFORM_WAIT_TIMES[platform]}s before executing the next {platform} action")
                    await asyncio.sleep(settings.PLATEFORM_WAIT_TIMES[platform])
                else:
                    print(
                        f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Skipping {platform} action for {airdrop_info['name']} due to delay constraint.")

    async def airdrop_execution(self, has_discord_action):
        if has_discord_action:
            await self.discord_handler.connect()

        while True:
            # Iterate through the airdrop files
            for airdrop in airdrop_info:
                if airdrop["isActivated"]:
                    print("------------------------")
                    message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Executing actions for {airdrop['name']} airdrop"
                    print(message)
                    await self.execute_airdrop_actions(airdrop)

                    # Message indicating that the actions for the current airdrop are finished
                    message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Finished actions for {airdrop['name']} airdrop"
                    print(message)

            # Message indicating that there is a waiting time before starting the next actions
            message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Waiting for {settings.INTERVAL}s before starting the next airdrop actions"
            print(message)
            await asyncio.sleep(settings.INTERVAL)

    async def close(self):
        if self.discord_handler.is_connected:
            await self.discord_handler.disconnect()

# Function to load airdrop files
def load_airdrop_files():
    airdrops_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "airdrops"))
    airdrop_files = [f for f in os.listdir(airdrops_path) if f.endswith(".py")]

    airdrop_list = []
    for airdrop_file in airdrop_files:
        file_path = os.path.join(airdrops_path, airdrop_file)
        spec = importlib.util.spec_from_file_location(airdrop_file[:-3], file_path)
        airdrop_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(airdrop_module)
        airdrop_list.append(airdrop_module.airdrop_info)

    return airdrop_list

# Load the airdrop files
airdrop_info = load_airdrop_files()

async def main():
    airdrop_bot = AirdropFarmer()
    await airdrop_bot.initialize()

    # Initialize the dispatcher and register handlers
    bot_instance = Bot(token=settings.TELEGRAM_TOKEN)
    dp = Dispatcher(bot_instance)
    register_handlers(dp)

    has_discord_action = any(action["platform"] == "discord" for airdrop in airdrop_info for action in airdrop["actions"])

    try:
        await airdrop_bot.airdrop_execution(has_discord_action)
    finally:
        await airdrop_bot.close()

asyncio.run(main())

