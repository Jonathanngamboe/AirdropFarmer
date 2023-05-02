from datetime import datetime
from asyncio import to_thread
import asyncio
from src import ipn_handler
from src.discord_handler import DiscordHandler
from src.telegram_bot import TelegramBot
import config.settings as settings
from src.db_manager import DBManager
from asyncpg.exceptions import ConnectionDoesNotExistError
import json
from quart import Quart, request
from hypercorn.asyncio import serve

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

ipn_handler_instance = None
telegram_bot = None

app = Quart(__name__)

@app.route('/ipn', methods=['POST'])
async def handle_ipn():
    global ipn_handler_instance
    global telegram_bot

    ipn_data = await request.form
    await ipn_handler_instance.handle_ipn(ipn_data, telegram_bot=telegram_bot)
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}

async def run_flask_app():
    await serve(app, host='127.0.0.1', port=settings.IPN_PORT)

async def main():
    global ipn_handler_instance
    global telegram_bot
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

    # Create a TelegramBot instance
    telegram_bot = TelegramBot(settings.TELEGRAM_TOKEN, db_manager)

    # Create an IPNHandler instance
    ipn_handler_instance = ipn_handler.IPNHandler(db_manager)

    # Run the Quart app in a separate thread
    quart_thread = asyncio.create_task(to_thread(run_flask_app))

    # Construct the IPN URL and print it out
    print(f"IPN URL: {settings.COINPAYMENTS_IPN_URL}")

    try:
        # Run the airdrop_execution coroutine concurrently with the Telegram bot
        await asyncio.gather(telegram_bot.dp.start_polling())
    except KeyboardInterrupt:
        print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')} INFO - Keyboard interrupt detected. Exiting...")
    finally:
        await airdrop_farmer.close()
        await telegram_bot.stop()  # Stop the Telegram bot
        quart_thread.join()  # Wait for the Flask thread to finish

asyncio.run(main())
