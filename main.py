from datetime import datetime
import asyncio
from src import ipn_handler
from src.discord_handler import DiscordHandler
from src.telegram_bot import TelegramBot
import config.settings as settings
from src.db_manager import DBManager
from asyncpg.exceptions import ConnectionDoesNotExistError
import json
from quart import Quart, request
import hypercorn
from hypercorn.asyncio import serve
from src.logger import Logger
import logging

class AirdropFarmer:
    def __init__(self):
        self.connected_to_discord_event = asyncio.Event()
        self.discord_handler = DiscordHandler(self.connected_to_discord_event)
        self.last_executed = {}  # Dictionary to store the last execution time

    async def initialize(self):
        message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Welcome to the Airdrop Farming Bot!"
        print(message)

    async def close(self):
        if self.discord_handler.is_connected:
            await self.discord_handler.disconnect()

app = Quart(__name__)

# Create an instance of the Logger class for system logs
system_logger = Logger(app_log=True)

@app.route('/ipn', methods=['POST'])
async def handle_ipn():
    ipn_data = await request.form
    print(f"IPN Handler instance: {ipn_handler_instance}")
    system_logger.add_log(f"IPN Handler instance: {ipn_handler_instance}", logging.INFO)
    await ipn_handler_instance.handle_ipn(ipn_data, telegram_bot=telegram_bot)
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}

async def run_flask_app():
    config = hypercorn.Config()
    config.bind = [
        "0.0.0.0:{}".format(settings.IPN_PORT)]  # Replace 127.0.0.1 with 0.0.0.0 to receive requests from outside
    await serve(app, config)


async def main():
    global ipn_handler_instance
    global telegram_bot

    # Initialize the database
    db_manager = DBManager()

    # Initialize global variables
    ipn_handler_instance = ipn_handler.IPNHandler(db_manager)
    telegram_bot = TelegramBot(settings.TELEGRAM_TOKEN, db_manager)
    print(f"IPNHandler instance created in main: {ipn_handler_instance}")
    system_logger.add_log(f"IPNHandler instance created in main: {ipn_handler_instance}", logging.INFO)

    for i in range(settings.MAX_DB_RETRIES):  # Try to connect to the database
        try:
            await db_manager.init_db()
            system_logger.add_log("Successfully connected to the database.", logging.INFO)
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Successfully connected to the database.")
            break
        except ConnectionDoesNotExistError as e:
            if i < settings.MAX_DB_RETRIES - 1:  # Check if it's not the last retry
                system_logger.add_log(f"Failed to connect to the database: {e}. Retrying in 5 seconds...",
                                      logging.WARNING)
                print(
                    f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} WARNING - Failed to connect to the database: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                system_logger.add_log(
                    f"Failed to connect to the database after {settings.MAX_DB_RETRIES} attempts. Exiting...",
                    logging.ERROR)
                print(
                    f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} ERROR - Failed to connect to the database after {settings.MAX_DB_RETRIES} attempts. Exiting...")
                return

    # Create an AirdropFarmer instance
    airdrop_farmer = AirdropFarmer()
    await airdrop_farmer.initialize()

    try:
        # Run the Quart app concurrently with the Telegram bot
        await asyncio.gather(run_flask_app(), telegram_bot.start_polling())
    except KeyboardInterrupt:
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Keyboard interrupt detected. Exiting...")
    finally:
        await airdrop_farmer.close()
        await telegram_bot.stop()  # Stop the Telegram bot

asyncio.run(main())
