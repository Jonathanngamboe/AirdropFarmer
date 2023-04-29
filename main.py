from datetime import datetime
import asyncio
from src.discord_handler import DiscordHandler
from src.telegram_bot import TelegramBot
import config.settings as settings
from src.db_manager import DBManager
from asyncpg.exceptions import ConnectionDoesNotExistError


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


async def main():
    # Initialize the database
    db_manager = DBManager()
    for i in range(settings.MAX_DB_RETRIES):  # Try to connect to the database
        try:
            await db_manager.init_db()
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Successfully connected to the database.")
            break
        except ConnectionDoesNotExistError as e:
            if i < settings.MAX_DB_RETRIES - 1:  # Check if it's not the last retry
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Failed to connect to the database: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Failed to connect to the database after {settings.MAX_DB_RETRIES} attempts. Exiting...")
                return

    # Create an AirdropFarmer instance
    airdrop_farmer = AirdropFarmer()
    await airdrop_farmer.initialize()

    # Create an asyncio.Event to synchronize the Telegram bot and the airdrop execution
    airdrop_event = asyncio.Event()

    # Create a TelegramBot instance
    telegram_bot = TelegramBot(settings.TELEGRAM_TOKEN, db_manager)

    try:
        # Run the airdrop_execution coroutine concurrently with the Telegram bot
        await asyncio.gather(telegram_bot.dp.start_polling())
    except KeyboardInterrupt:
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Keyboard interrupt detected. Exiting...")
    finally:
        await airdrop_farmer.close()
        await telegram_bot.stop()  # Stop the Telegram bot

asyncio.run(main())

