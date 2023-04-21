# telegram_bot.py

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ParseMode
from config import settings
from typing import List
import logging

from src.user import User  # Import the User class

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token, db_manager):
        self.bot = Bot(token=token)
        self.db_manager = db_manager
        self.dp = Dispatcher(self.bot)
        self.register_handlers()

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_start_farming, commands=["start_farming"])
        self.dp.register_callback_query_handler(self.on_menu_button_click)

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name

        user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)
        if user is None:
            user = await User.create_user(telegram_id, username, self.db_manager)

        welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n📚 Detailed Guide: Guide\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"

        await self.send_menu(message.chat.id, 'main', message=welcome_text) # Send the main menu

    async def on_menu_button_click(self, query: CallbackQuery):
        data = query.data.split(':')
        action = data[0]
        menu = data[1] if len(data) > 1 else None

        if action == 'menu':
            if menu == 'main':
                username = query.from_user.full_name
                welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n📚 Detailed Guide: Guide\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"
                await self.send_menu(query.from_user.id, menu, message=welcome_text, message_id=query.message.message_id)
            else:
                await self.send_menu(query.from_user.id, menu, message_id=query.message.message_id)
        elif action == 'add_airdrop':
            await self.cmd_add_airdrop(query) # Handle the add_airdrop action
        elif action == 'start_farming':
            await self.cmd_start_farming(query.message) # Handle the start_farming action
        # Add more actions as needed

        await query.answer()

    async def send_menu(self, chat_id, menu, message="Choose an option:",message_id=None):
        keyboard = InlineKeyboardMarkup(row_width=2)
        if menu == 'main':
            keyboard.add(
                InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"),
                InlineKeyboardButton("💸 Manage airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("💳 Subscription", callback_data="menu:manage_subscription"),
                InlineKeyboardButton("👛 Manage wallets", callback_data="menu:manage_wallets"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings")
            )
        elif menu == 'manage_airdrops':
            keyboard.add(
                InlineKeyboardButton("➕ Add new airdrop", callback_data="menu:add_airdrop"),
                InlineKeyboardButton("✏️ Edit airdrops", callback_data="menu:edit_airdrops"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'add_airdrop':
            available_airdrops = ["Base", "Scroll", "Arbitrum", "Zksync"]
            telegram_id = chat_id
            user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)
            if user.airdrops:
                available_airdrops = list(set(available_airdrops) - set(user.airdrops))

            if available_airdrops:
                for airdrop in available_airdrops:
                    keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"add_airdrop:{airdrop}"))
                message = "Select the airdrop(s) you want to farm:"
            else:
                message = "There are currently no airdrops to farm.\nCheck your airdrops list to see which airdrops you are farming."

            keyboard.add(
                InlineKeyboardButton("🔙 Back", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("🏠 Main menu", callback_data="menu:main"))
        elif menu == 'manage_wallets':
            keyboard.add(
                InlineKeyboardButton("➕ Add wallet", callback_data="menu:add_wallet"),
                InlineKeyboardButton("✏️ Manage wallets", callback_data="menu:manage_wallets"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'manage_subscription':
            keyboard.add(
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'settings':
            keyboard.add(
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        # Add more menus as needed
        else:
            return

        if message_id:
            await self.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"{message}",
                                             reply_markup=keyboard)
        else:
            await self.bot.send_message(chat_id=chat_id, text=f"{message}", reply_markup=keyboard)

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

    async def cmd_start_farming(self, message: types.Message):
        print("Start farming")
        pass

    async def cmd_add_airdrop(self, query: CallbackQuery):
        data = query.data.split(':')
        airdrop_name = data[1] if len(data) > 1 else None

        if airdrop_name:
            telegram_id = query.from_user.id
            user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)

            if not user.airdrops:
                user.airdrops = []

            user.airdrops.append(airdrop_name)
            await user.update_airdrops(self.db_manager)

            message = f"{airdrop_name} airdrop added to your list."
            await self.bot.send_message(chat_id=telegram_id, text=message)
            await self.send_menu(telegram_id, 'add_airdrop', message="Select the airdrop(s) you want to farm:")

    async def stop(self):
        await self.bot.close()
