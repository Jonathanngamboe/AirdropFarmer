import asyncio
from quart import Quart, request
from src.db_manager import DBManager
from src.discord_handler import DiscordHandler
from src.ipn_handler import IPNHandler
from src.logger import Logger
from src.telegram_bot import TelegramBot
from asyncpg.exceptions import ConnectionDoesNotExistError
from hypercorn.asyncio import serve
import hypercorn
import config.settings as settings
from datetime import datetime
import json
import logging

class AirdropFarmer:
    def __init__(self):
        self.connected_to_discord_event = asyncio.Event()
        self.discord_handler = DiscordHandler(self.connected_to_discord_event)
        self.last_executed = {}  # Dictionary to store the last execution time

    async def initialize(self):
        message = f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Welcome to the Airdrop Farming Bot!"
        system_logger.add_log(message, logging.INFO)

    async def close(self):
        if self.discord_handler.is_connected:
            await self.discord_handler.disconnect()

async def check_subscriptions_periodically(db_manager):
    while True:
        await db_manager.check_and_update_expired_subscriptions()
        await asyncio.sleep(86400)  # Sleep for a day

app = Quart(__name__)

# Create an instance of the Logger class for system logs
system_logger = Logger(app_log=True)

async def run_flask_app(app, ipn_handler_instance, telegram_bot):
    @app.route('/ipn', methods=['POST'])
    async def handle_ipn_route():
        ipn_data = await request.form
        await ipn_handler_instance.handle_ipn(ipn_data, telegram_bot=telegram_bot)
        return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}

    config = hypercorn.Config()
    config.bind = [
        "0.0.0.0:{}".format(settings.IPN_PORT)]  # Replace 127.0.0.1 with 0.0.0.0 to receive requests from outside
    await serve(app, config)

async def main():
    # Initialize the database
    db_manager = DBManager(system_logger)

    # Initialize instances
    ipn_handler_instance = IPNHandler(db_manager, system_logger)
    telegram_bot = TelegramBot(settings.TELEGRAM_TOKEN, db_manager, system_logger)

    for i in range(settings.MAX_DB_RETRIES):  # Try to connect to the database
        try:
            await db_manager.init_db()
            system_logger.add_log("Successfully connected to the database.", logging.INFO)
            break
        except ConnectionDoesNotExistError as e:
            if i < settings.MAX_DB_RETRIES - 1:  # Check if it's not the last retry
                system_logger.add_log(f"Failed to connect to the database: {e}. Retrying in 5 seconds...",
                                      logging.WARNING)
                await asyncio.sleep(5)
            else:
                system_logger.add_log(f"Failed to connect to the database after {settings.MAX_DB_RETRIES} attempts. Exiting...",
                    logging.ERROR)
                return

    # Create an AirdropFarmer instance
    airdrop_farmer = AirdropFarmer()
    await airdrop_farmer.initialize()

    tasks = []
    try:
        # Run the Quart app concurrently with the Telegram bot
        tasks.append(asyncio.create_task(run_flask_app(app, ipn_handler_instance, telegram_bot)))
        tasks.append(asyncio.create_task(telegram_bot.start_polling()))
        tasks.append(asyncio.create_task(check_subscriptions_periodically(db_manager)))
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        system_logger.add_log("Keyboard interrupt detected. Exiting...", logging.INFO)
    except Exception as e:
        system_logger.add_log(f"An unexpected error occurred: {e}", logging.ERROR)
    finally:
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await airdrop_farmer.close()
        await telegram_bot.stop()  # Stop the Telegram bot

asyncio.run(main())