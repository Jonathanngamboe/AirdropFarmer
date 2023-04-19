from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.types import ParseMode
from config import settings
import logging

from src.user import User  # Import the User class

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(self.bot)
        self.register_handlers()

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_action1, commands=["action1"])
        self.dp.register_message_handler(self.cmd_action2, commands=["action2"])
        self.dp.register_message_handler(self.cmd_action3, commands=["action3"])

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name
        user = await User.get_user_by_telegram_id(telegram_id)

        if not user:
            user = await User.create_user(telegram_id)

        subscription_info = user.get_subscription_info()
        welcome_text = f"🤖 Welcome, {username}! You're using the Airdrop Farmer Bot. 🤖\n\nYour subscription level: {subscription_info['level']}\nFeatures available: {', '.join(subscription_info['features'])}\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"

        await message.reply(welcome_text, parse_mode=ParseMode.HTML)

    async def cmd_action1(self, message: types.Message):
        # Code to execute action 1
        await message.reply("Action 1 executed")

    async def cmd_action2(self, message: types.Message):
        # Code to execute action 2
        await message.reply("Action 2 executed")

    async def cmd_action3(self, message: types.Message):
        # Code to execute action 3
        await message.reply("Action 3 executed")

    async def start_polling(self):
        from aiogram import types
        from aiogram.utils import executor

        async def on_startup(dp):
            await self.bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text="Bot has been started")

        async def on_shutdown(dp):
            await self.bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text="Bot has been stopped")

            # Remove webhook (if set)
            await self.bot.delete_webhook()

            # Close db connection (if used)
            await dp.storage.close()
            await dp.storage.wait_closed()

        executor.start_polling(self.dp, on_startup=on_startup, on_shutdown=on_shutdown)

    async def stop(self):
        await self.bot.close()
