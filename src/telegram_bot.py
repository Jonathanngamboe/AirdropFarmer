from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ParseMode
from config import settings
import logging

from src.user import User  # Import the User class

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token, db_manager):
        self.welcome_text = None
        self.bot = Bot(token=token)
        self.db_manager = db_manager
        self.dp = Dispatcher(self.bot)
        self.register_handlers()

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_start_airdrops, commands=["start_airdrops"])
        self.dp.register_callback_query_handler(self.on_menu_button_click)

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name
        user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)

        if not user:
            user = await User.create_user(telegram_id, username, self.db_manager)

        self.welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n📚 Detailed Guide: Guide\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"

        await self.send_menu(message.chat.id, 'main', message=self.welcome_text) # Send the main menu

    async def on_menu_button_click(self, query: CallbackQuery):
        data = query.data.split(':')
        action = data[0]
        menu = data[1]

        if action == 'menu':
            await self.send_menu(query.from_user.id, menu, message_id=query.message.message_id)
        if action == 'start_farming':
            await self.cmd_start_farming(query.message)
        elif action == 'edit_airdrops':
            await self.cmd_edit_airdrops(query.message)
        elif action == 'manage_subscription':
            # Add your code to handle manage_subscription action
            pass
        elif action == 'edit_wallets':
            await self.cmd_edit_wallets(query.message)
        elif action == 'settings':
            # Add your code to handle settings action
            pass
        # Add more actions as needed

        await query.answer()

    async def send_menu(self, chat_id, menu, message="Choose an option:",message_id=None):
        if menu == 'main':
            message = self.welcome_text
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🚀 Start farming", callback_data="menu:start_farming"),
                InlineKeyboardButton("💸 Edit airdrops", callback_data="menu:edit_airdrops"),
                InlineKeyboardButton("💳 Subscription", callback_data="menu:manage_subscription"),
                InlineKeyboardButton("👛 Edit wallets", callback_data="menu:edit_wallets"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings")
            )
        elif menu == 'edit_airdrops':
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("➕ Select new airdrop", callback_data="select_airdrop"),
                InlineKeyboardButton("✏️ Edit airdrops", callback_data="edit_airdrops"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'edit_wallets':
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("➕ Add wallet", callback_data="add_wallet"),
                InlineKeyboardButton("✏️ Edit wallets", callback_data="edit_wallets"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'manage_subscription':
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'settings':
            keyboard = InlineKeyboardMarkup(row_width=2)
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

    async def cmd_start_airdrops(self, message: types.Message):
        # Extract the selected airdrop names from the message text
        selected_airdrops = message.text.split()[1:]

        # Call the start_selected_airdrops method of AirdropFarmer
        self.airdrop_farmer.start_selected_airdrops(selected_airdrops)

        await message.reply("Starting selected airdrops")

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
