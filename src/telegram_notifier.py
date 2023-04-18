# telegram_notifier.py
from requests import Request
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from config import settings
from aiogram import Bot, Dispatcher, types
import logging

logging.basicConfig(level=logging.INFO)


class TelegramNotifier:
    def __init__(self, timeout=None):
        request = Request()
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.bot = Bot(token=settings.TELEGRAM_TOKEN)
        self.dp = Dispatcher(self.bot)

    async def send_message(self, message):
        await self.bot.send_message(chat_id=self.chat_id, text=message)

    async def on_startup(self, dp):
        await self.bot.send_message(chat_id=self.chat_id, text="Bot has been started")

    async def on_shutdown(self):
        await self.bot.send_message(chat_id=self.chat_id, text="Bot has been stopped")
        session = await self.bot.get_session()
        await session.close()

    async def notify_success(self, airdrop_name):
        message = f"Successfully completed actions for {airdrop_name}."
        await self.bot.send_message(chat_id=self.chat_id, text=message)

    async def notify_error(self, airdrop_name, error_message):
        message = f"Error occurred while processing {airdrop_name}: {error_message}"
        await self.bot.send_message(chat_id=self.chat_id, text=message)

    async def notify_captcha_required(self):
        message = "Captcha required for Discord. Please complete the captcha."
        await self.bot.send_message(chat_id=self.chat_id, text=message)
