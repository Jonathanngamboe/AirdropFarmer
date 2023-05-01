# telegram_bot.py
import asyncio
import os
from collections import defaultdict
from aiogram.utils import executor
from aiogram import Bot, Dispatcher, types
from aiogram.utils.exceptions import InvalidQueryID, MessageNotModified
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ParseMode
from config import settings
import logging
from ecdsa import SECP256k1
from eth_keys import keys
from src.airdrop_execution import AirdropExecution
from src.discord_handler import DiscordHandler
from src.logger import Logger
from src.user import User
from aiogram.types import InputFile
import re

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token, db_manager):
        self.bot = Bot(token=token)
        self.db_manager = db_manager
        self.dp = Dispatcher(self.bot)
        self.register_handlers()
        self.farming_users = {} # Used to keep track of the users that are farming
        self.user_airdrop_executions = defaultdict(dict)
        self.airdrop_events = defaultdict(asyncio.Event)
        self.discord_handler = DiscordHandler(self.airdrop_events)
        self.user_loggers = {} # Used to store Logger instances for each user
        self.register_handlers()
        self.welcome_text = "\nHow to use the bot?\n\n📚 Detailed Guide: https://defi-bots.gitbook.io/airdrop-farmer/\n\n📤 If you have any questions, suggestions, or need assistance, please type /contact to reach us. We're always here to help!"
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5
        self.contact_text = "If you need help using the bot, please visit our wiki: https://defi-bots.gitbook.io/airdrop-farmer/\n\nIf you have a specific question or want to discuss your suscription plan, click the button below."

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_show_main_menu, Command(["menu"]))
        self.dp.register_message_handler(self.cmd_stop, commands=['stop'], commands_prefix='/', state='*')
        self.dp.register_message_handler(self.cmd_contact, commands=['contact'], commands_prefix='/', state='*')
        self.dp.register_message_handler(self.cmd_add_wallet, Command("add_wallet"), content_types=types.ContentTypes.TEXT)
        self.dp.register_callback_query_handler(self.on_menu_button_click)

    async def start_polling(self):
        async def on_startup(dp):
            pass
            # await self.bot.send_message(chat_id=, text="Bot has been started")

        async def on_shutdown(dp):
            # Remove webhook (if set)
            await self.bot.delete_webhook()

            # Close db connection (if used)
            await dp.storage.close()
            await dp.storage.wait_closed()

        executor.start_polling(self.dp, on_startup=on_startup, on_shutdown=on_shutdown)

    async def get_user(self, telegram_id, username=None):
        user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)
        if user is None:
            user = await User.create_user(telegram_id, username, self.db_manager)
        return user

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name

        user_logger = self.get_user_logger(telegram_id)  # This will create the logger instance for the user if it doesn't already exist
        user_logger.add_log(f"User {username} (ID: {telegram_id}) started the bot.")

        self.welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n\n📚 Detailed Guide: https://defi-bots.gitbook.io/airdrop-farmer/\n\n📤 If you have any questions, suggestions, or need assistance, please type /contact to reach us. We're always here to help!"

        await self.send_menu(message.chat.id, 'main', message=self.welcome_text) # Send the main menu

    async def cmd_stop(self, message: types.Message):
        user_id = message.from_user.id
        await self.bot.send_message(user_id, "Goodbye! The bot has been stopped. If you want to start again, just type /start")
        # Remove the user from the current state

    async def cmd_contact(self, message: types.Message, user_id: int = None):
        if user_id is None:
            user_id = message.from_user.id

        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Back to menu", callback_data="menu:main"),
            InlineKeyboardButton("💬 Write us here", callback_data="contact_us")
        )
        await self.bot.send_message(user_id, self.contact_text, reply_markup=keyboard)

    async def cmd_send_contact_message(self, message: types.Message):
        user_id = message.from_user.id
        admin_id = settings.ADMIN_TELEGRAM_ID
        user_message = message.text
        if user_message.lower() == "cancel":
            await self.bot.send_message(user_id, "Contact request canceled.")
        else:
            await self.bot.send_message(admin_id,
                                        f"Message from {message.from_user.full_name} (ID: {user_id}): {user_message}")
            await self.bot.send_message(user_id, "Your message has been sent to our support team. We will get back to you as soon as possible.")
        await self.send_menu(user_id, 'main', message=self.welcome_text)

    async def cmd_show_main_menu(self, message: types.Message):
        await self.send_menu(message.chat.id, 'main',message=self.welcome_text) # Send the main menu

    async def on_menu_button_click(self, query: CallbackQuery):
        data = query.data.split(':')
        action = data[0]
        sub_data = data[1] if len(data) > 1 else None
        if action == 'menu':
            if sub_data == 'main':
                await self.send_menu(query.from_user.id, sub_data, message=self.welcome_text,
                                     message_id=query.message.message_id)
            elif sub_data == 'add_wallet':
                await self.display_wallet_warning(query.message)  # Display the warning message before adding a wallet
            elif sub_data == 'show_logs':
                await self.send_menu(query.from_user.id, sub_data, message_id=query.message.message_id)
            else:
                await self.send_menu(query.from_user.id, sub_data, message_id=query.message.message_id)
        elif action == 'add_airdrop':
            await self.cmd_add_airdrop(query)  # Handle the add_airdrop action
        elif action == 'show_airdrop':  # Add the show_airdrop action
            await self.cmd_show_airdrop_details(query, airdrop_name=sub_data)
        elif action == 'edit_airdrop':
            await self.cmd_edit_airdrop(query, airdrop_name=sub_data)
        elif action == 'remove_airdrop':
            await self.cmd_remove_airdrop(query, sub_data)
        elif action == 'edit_wallets':
            await self.cmd_edit_wallets(query)  # Handle the edit_wallets action
        elif action == 'remove_wallet':
            await self.cmd_remove_wallet(query, sub_data)
        elif action == 'start_farming':
            await self.cmd_start_farming(query.from_user.id, query.message.chat.id, query.message.message_id)
        elif action == "stop_farming":
            await self.cmd_stop_farming(query.from_user.id, query.message.chat.id, query.message.message_id)
        elif action == "display_log":
            await self.cmd_display_log(query.from_user.id, query.message.chat.id, sub_data, query.message.message_id)
        elif action == "contact_us":  # Add this new block to handle the contact_us action
            user_id = query.from_user.id
            await self.bot.send_message(user_id, "Please type your message in the chat or type 'cancel' to cancel:")
            # Register the cmd_send_contact_message handler for the user's next message
            self.dp.register_message_handler(self.cmd_send_contact_message, lambda msg: msg.from_user.id == user_id)
        # Add more actions as needed

        await self.retry_request(self.bot.answer_callback_query, query.id)

    async def retry_request(self, func, *args, **kwargs):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                return await func(*args, **kwargs)
            except InvalidQueryID as e:
                print(f"WARNING - Query is too old or query ID is invalid: {e}")
                return None  # Stop retrying as this exception won't likely resolve on its own
            except Exception as e:
                retries += 1
                print(f"WARNING - Retrying request due to error: {e}")
                await asyncio.sleep(self.RETRY_DELAY)
        print(f"ERROR - Request failed after {self.MAX_RETRIES} retries.")
        return None

    async def send_menu(self, chat_id, menu, message="Choose an option:",message_id=None):
        user = await self.get_user(chat_id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []
        user_wallets = await user.get_wallets(self.db_manager) if await user.get_wallets(self.db_manager) else []
        keyboard = InlineKeyboardMarkup(row_width=2)
        if menu == 'main':
            keyboard.add(
                InlineKeyboardButton("💸 My airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("👛 My wallets", callback_data="menu:manage_wallets"),
                InlineKeyboardButton("💳 Subscription", callback_data="menu:manage_subscription"),
                InlineKeyboardButton("📋 Logs", callback_data="menu:show_logs"),
                InlineKeyboardButton("📤 Contact", callback_data="menu:contact"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
                InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"),
            )
        elif menu == 'manage_airdrops':
            # Create a temporary instance to get the active airdrops
            temp_airdrop_execution = AirdropExecution(None, None, None)
            available_airdrops = temp_airdrop_execution.get_active_airdrops()
            available_airdrop_names = [airdrop["name"] for airdrop in available_airdrops]
            # Remove user airdrops that are no longer active from the database
            for airdrop in user_airdrops:
                if airdrop not in available_airdrop_names:
                    await user.remove_airdrop(airdrop, self.db_manager)

            keyboard.add(
                InlineKeyboardButton("✏️ Edit my airdrops", callback_data="menu:edit_airdrops"),
                InlineKeyboardButton("➕ Add new airdrop", callback_data="menu:add_airdrop"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main"),
            )
        elif menu == 'add_airdrop':
            # Create a temporary instance to get the active airdrops
            temp_airdrop_execution = AirdropExecution(None, None, None)
            available_airdrops = temp_airdrop_execution.get_active_airdrops()

            available_airdrop_names = [airdrop["name"] for airdrop in available_airdrops]

            # Calculate the remaining airdrops that the user can add
            remaining_airdrops = [airdrop for airdrop in available_airdrop_names if airdrop not in user_airdrops]

            if remaining_airdrops:
                for airdrop in remaining_airdrops:
                    keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"show_airdrop:{airdrop}"))
                message = "Select the airdrop you want to farm:"
            else:
                message = "There are currently no additional airdrops to farm. Check your airdrops list to see which airdrops you are farming."
            keyboard.add(
                InlineKeyboardButton("🔙 Back to manage airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("🏠 Main menu", callback_data="menu:main")
            )
        elif menu == 'edit_airdrops':
            if user_airdrops:
                if len(user_airdrops) > 1:
                    message = "Your airdrops (click on an airdrop to edit it):"
                else:
                    message = "Your airdrop (click on the airdrop to edit it):"
            else:
                message = "You don't have any airdrops yet. Add an airdrop to start farming."
            for airdrop in user_airdrops:
                keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"edit_airdrop:{airdrop}"))

            keyboard.add(
                InlineKeyboardButton("🔙 Back to manage airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("🏠 Main menu", callback_data="menu:main"))
        elif menu == 'manage_wallets':
            if user_wallets:
                if len(user_wallets) > 1:
                    message = "Your wallets (click on a wallet to remove it):"
                else:
                    message = "Your wallet (click on the wallet to remove it):"
            else:
                message = "You don't have any wallets yet. Add a wallet to start farming."

            for wallet in user_wallets:
                keyboard.add(InlineKeyboardButton(wallet['name'], callback_data=f"remove_wallet:{wallet['name']}"))

            keyboard.add(
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main"),
                InlineKeyboardButton("➕ Add wallet", callback_data="menu:add_wallet"),
            )
        elif menu == 'contact':
            await self.cmd_contact(user_id=chat_id)
        elif menu == 'show_logs':
            user_logger = self.get_user_logger(chat_id)
            log_dates = user_logger.get_log_dates()

            if not log_dates:
                await self.bot.send_message(chat_id, "No logs found.")
                return

            keyboard = InlineKeyboardMarkup(row_width=1)
            for date in log_dates:
                keyboard.add(InlineKeyboardButton(date, callback_data=f"display_log:{date}"))

            keyboard.add(InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main"))

            message = "Select a date to view the logs:"
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

    async def cmd_display_log(self, user_id, chat_id, log_date, message_id=None):
        user_logger = Logger(user_id)
        date_str = log_date.replace(f"user_{user_id}_", "").replace(".log", "")
        log_file_path = user_logger.get_log_file_path(date_str)

        if log_file_path.exists():
            with log_file_path.open('rb') as log_file:
                await self.bot.send_document(chat_id, InputFile(log_file), caption=f"Logs for {date_str}")
        else:
            await self.bot.send_message(chat_id, f"No logs found for {date_str}")

    async def cmd_start_farming(self, user_id, chat_id, message_id):
        user = await self.get_user(user_id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []
        user_wallets = await user.get_wallets(self.db_manager)

        if user_id in self.farming_users.keys():
            await self.bot.send_message(chat_id, "Airdrop farming is already in progress. Please wait or press the 'Stop farming' button to stop.")
            return

        if not user_airdrops:
            await self.bot.send_message(chat_id, "You must have at least one airdrop registered to start farming.")
            return

        if not user_wallets:
            await self.bot.send_message(chat_id, "You must have at least one wallet registered to start farming.")
            return

        airdrop_execution = AirdropExecution(self.discord_handler, self.get_user_logger(user_id), user_wallets)
        active_airdrops = airdrop_execution.get_active_airdrops()

        active_airdrop_names = [airdrop["name"] for airdrop in active_airdrops]
        valid_airdrops = [airdrop for airdrop in user_airdrops if airdrop in active_airdrop_names]
        if not valid_airdrops:
            await self.bot.send_message(chat_id, "You must have at least one active airdrop registered to start farming.")
            return

        self.farming_users[user_id] = {
            'status': True,
            'message_id': message_id
        }
        await self.bot.send_message(chat_id, "Airdrop farming started.")

        await self.update_keyboard_layout(user_id)

        airdrop_execution.airdrops_to_execute = valid_airdrops

        airdrop_execution_task = asyncio.create_task(airdrop_execution.airdrop_execution())
        self.user_airdrop_executions[user_id] = (airdrop_execution, airdrop_execution_task)

        asyncio.create_task(self.notify_airdrop_execution(user_id))

    async def cmd_stop_farming(self, user_id, chat_id, message_id):
        if user_id in self.farming_users.keys():
            airdrop_execution, airdrop_execution_task = self.user_airdrop_executions.get(user_id, (None, None))
            if airdrop_execution:
                airdrop_execution.stop_requested = True
                self.get_user_logger(user_id).add_log("WARNING - Stop farming requested.")
                await self.bot.send_message(chat_id, "Stopping airdrop farming. This may take a few minutes. Please wait...")
                await asyncio.gather(airdrop_execution_task)
                await self.update_keyboard_layout(chat_id)
            else:
                await self.bot.send_message(chat_id, "Airdrop farming is not running.")
        else:
            await self.bot.send_message(chat_id, "Airdrop farming is not running.")
            return

    async def notify_airdrop_execution(self, user_id):
        # Verify if the airdrop execution has finished and notify the user
        while not self.user_airdrop_executions[user_id][0].finished:
            await asyncio.sleep(1)

        user = await self.get_user(user_id)
        airdrop_results = self.user_airdrop_executions[user_id][0].airdrop_statuses
        airdrop_execution = self.user_airdrop_executions[user_id][0]

        if not airdrop_execution.stop_requested:
            for airdrop_name, status in airdrop_results.items():
                if status:
                    await self.bot.send_message(user.telegram_id,
                                                f"Airdrop '{airdrop_name}' executed successfully. Check the logs for more details.")
                else:
                    await self.bot.send_message(user.telegram_id,
                                                f"Error executing airdrop '{airdrop_name}'. Check the logs for more details.")
        else:
            await self.bot.send_message(user.telegram_id, "Airdrop farming has been successfully stopped.")
            await asyncio.sleep(1)  # Add a short delay before updating the keyboard layout and displaying the menu

        self.farming_users[user_id]['status'] = False
        await self.update_keyboard_layout(user_id)
        await self.send_menu(user_id, 'main', message=self.welcome_text)

        del self.user_airdrop_executions[user_id]
        del self.farming_users[user_id]

    async def update_keyboard_layout(self, chat_id, menu='main'):
        user_id = chat_id  # Assuming the chat_id corresponds to the user_id in this case
        message_id = self.farming_users[user_id]['message_id']  # Get the old stored message_id
        if menu == 'main':
            keyboard = types.InlineKeyboardMarkup()
            if self.farming_users[user_id]['status']: # If the user is farming, show the 'Stop farming' button
                keyboard.add(types.InlineKeyboardButton("🛑 Stop farming", callback_data="stop_farming"))
            else:
                keyboard.add(types.InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"))

            try:
                await self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
            except MessageNotModified:
                print("Message not modified: new keyboard layout is the same as the current one.")

    def get_user_logger(self, user_id):
        if user_id not in self.user_loggers:
            self.user_loggers[user_id] = Logger(user_id)
        return self.user_loggers[user_id]

    async def cmd_show_airdrop_details(self, query: CallbackQuery, airdrop_name: str):
        # Replace this with the actual airdrop descriptions
        airdrop_descriptions = {
            "Base": "Base airdrop description...",
            "Scroll": "Scroll airdrop description...",
            "Arbitrum": "Arbitrum airdrop description...",
            "Zksync": "Zksync airdrop description...",
        }

        description = airdrop_descriptions.get(airdrop_name, "Airdrop description not found.")
        message = f"Airdrop: {airdrop_name}\n\n{description}\n\nDo you want to add this airdrop to your list?"

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🔙 Back to list", callback_data="menu:add_airdrop"),
            InlineKeyboardButton("✅ Add airdrop", callback_data=f"add_airdrop:{airdrop_name}"),
            InlineKeyboardButton("🏠 Main menu", callback_data="menu:main"),
        )

        await self.bot.edit_message_text(chat_id=query.from_user.id, message_id=query.message.message_id, text=message,
                                         reply_markup=keyboard)

    async def cmd_edit_airdrop(self, query: CallbackQuery, airdrop_name: str):
        # Replace this with the actual airdrop descriptions and editable parameters
        airdrop_data = {
            "Base": {"description": "Base airdrop description...", "editable_params": ["param1", "param2"]},
            "Scroll": {"description": "Scroll airdrop description...", "editable_params": ["param1", "param2"]},
            "Arbitrum": {"description": "Arbitrum airdrop description...", "editable_params": ["param1", "param2"]},
            "Zksync": {"description": "Zksync airdrop description...", "editable_params": ["param1", "param2"]},
        }

        airdrop_info = airdrop_data.get(airdrop_name,
                                        {"description": "Airdrop description not found.", "editable_params": []})

        message = f"Airdrop: {airdrop_name}\n\n{airdrop_info['description']}\n\nEditable parameters: {', '.join(airdrop_info['editable_params'])}\n\nDo you want to edit or remove this airdrop?"

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✏️ Edit params", callback_data=f"edit_airdrop_params:{airdrop_name}"),
            InlineKeyboardButton("❌ Remove", callback_data=f"remove_airdrop:{airdrop_name}"),
            InlineKeyboardButton("🔙 Back to list", callback_data="menu:edit_airdrops")
        )

        await self.bot.edit_message_text(chat_id=query.from_user.id, message_id=query.message.message_id, text=message,
                                         reply_markup=keyboard)

    async def cmd_add_airdrop(self, query: CallbackQuery):
        data = query.data.split(':')
        airdrop_name = data[1] if len(data) > 1 else None

        user = await self.get_user(query.from_user.id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []

        if airdrop_name not in user_airdrops : # and airdrop_name in self.airdrop_execution.get_airdrops()[]:
            await user.add_airdrop(airdrop_name, self.db_manager)
            message = f"{airdrop_name} airdrop added to your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_menu(query.from_user.id, 'add_airdrop', message="Select the airdrop you want to farm:")

    async def cmd_remove_airdrop(self, query: CallbackQuery, airdrop_name: str):
        user = await self.get_user(query.from_user.id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []
        if user_airdrops and airdrop_name in user_airdrops:
            await user.remove_airdrop(airdrop_name, self.db_manager)
            message = f"{airdrop_name} airdrop removed from your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_airdrop_edit_menu(query.from_user.id)
        else:
            message = f"{airdrop_name} airdrop not found in your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)

    async def cmd_add_wallet(self, message: types.Message):
        user = await self.get_user(message.from_user.id)
        user_wallets = await user.get_wallets(self.db_manager)
        split_message = message.text.split(" ", 1)
        if len(split_message) > 1:
            wallet_info = split_message[1].split(':', 1)
            if len(wallet_info) == 2:
                wallet_name, private_key = wallet_info
                # Remove leading and trailing spaces
                wallet_name = wallet_name.strip()
                private_key = private_key.strip()
                if not self.is_valid_wallet_name(wallet_name):
                    await message.reply(
                        f"Invalid wallet name. Please use only alphanumeric characters and underscores, with a maximum length of {settings.MAX_WALLET_NAME_LENGTH} characters and without spaces.\nType /add_wallet to try again.")
                    await message.delete()  # Delete the message containing the private key for security reasons
                    return
            else:
                # Handle the case where the input format is incorrect
                await message.reply("Please provide the wallet information in the format wallet_name:private_key")
                await message.delete()  # Delete the message containing the private key for security reasons
                return
        else:
            # Handle the case where nothing is provided after the command add_wallet
            await message.reply("Please provide a wallet name folooed by a colon and your private key.\nType /add_wallet to try again.")
            return

        wallet = await self.check_private_key(private_key)
        if not wallet: # If the private key is invalid
            await message.reply("Invalid private key. Please try again.\nType /add_wallet to try again.")
            return

        # Check if the wallet name is already in use
        if any(w['name'] == wallet_name for w in user_wallets):
            await message.reply("The wallet name is already in use. Please choose a different name.\nType /add_wallet to try again.")
            await message.delete()  # Delete the message containing the private key for security reasons
            return

        # Store the encrypted private key and wallet name in the user's database
        formatted_wallet_name = f"{wallet_name} ({wallet['public_key'][:4]}...{wallet['public_key'][-4:]})"
        wallet['name'] = formatted_wallet_name

        # Store the private key in the user's database
        if wallet not in user_wallets:
            await user.add_wallet(wallet, self.db_manager)
            # Send a confirmation message
            await message.reply("Wallet added successfully!", parse_mode=ParseMode.HTML)
        else:
            await message.reply("This wallet is already added.")

        await message.delete() # Delete the message containing the private key for security reasons

        await self.send_menu(message.from_user.id, 'manage_wallets')

    async def cmd_remove_wallet(self, query: CallbackQuery, wallet_name):
        user = await self.get_user(query.from_user.id)
        user_wallets = await user.get_wallets(self.db_manager)
        wallet = next((wallet for wallet in user_wallets if wallet['name'] == wallet_name), None)
        if wallet in user_wallets:
            await user.remove_wallet(wallet, self.db_manager)
            message = f"Wallet {wallet['name']} removed successfully!"
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_menu(query.from_user.id, 'manage_wallets')
        else:
            message = f"Wallet {wallet_name} not found in your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)

    async def is_valid_private_key(self, private_key_hex):
        try:
            private_key_int = int(private_key_hex, 16)
            return 0 < private_key_int < SECP256k1.order
        except ValueError:
            return False

    async def private_to_public_key(self, private_key_hex):
        private_key = keys.PrivateKey(bytes.fromhex(private_key_hex))
        public_key = private_key.public_key
        ethereum_address = public_key.to_checksum_address()
        return ethereum_address

    async def check_private_key(self, private_key_hex):
        if await self.is_valid_private_key(private_key_hex):
            public_key_hex = await self.private_to_public_key(private_key_hex)
            return {'private_key': private_key_hex, 'public_key': public_key_hex}
        else:
            return False

    def is_valid_wallet_name(self, name: str) -> bool:
        if len(name) > settings.MAX_WALLET_NAME_LENGTH:
            return False
        # Ensure the name contains only alphanumeric characters and underscores
        return re.match(r'^\w+$', name) is not None

    async def display_wallet_warning(self, message: types.Message):
        warning_text = (
            "⚠️ WARNING: Sharing your private key involves risks. We do everything possible to ensure your private key never falls into the wrong hands. However, you should follow these safety measures:\n\n"
            "- Create a new wallet dedicated to the use of this bot.\n"
            "- Never use your main wallet.\n"
            "- Leave only the necessary funds for transactions in the wallet.\n"
            "- After receiving an airdrop, immediately secure it by sending it to another wallet for which you are the only one with the private key.\n"
            "\nIf you understand the risks and still wish to proceed, type /add_wallet followed by your wallet name and private key. For example: wallet_name:private_key\n"
        )
        await message.reply(warning_text)

    async def send_airdrop_edit_menu(self, telegram_id):
        keyboard = InlineKeyboardMarkup(row_width=1)
        user = await self.get_user(telegram_id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []

        if user_airdrops:
            for airdrop in user_airdrops:
                keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"edit_airdrop:{airdrop}"))
        else:
            message = "Your airdrop list is empty."
            await self.bot.send_message(chat_id=telegram_id, text=message)
            await self.send_menu(telegram_id, 'manage_airdrops')
            return

        keyboard.add(
            InlineKeyboardButton("🔙 Back to manage airdrops", callback_data="menu:manage_airdrops"),
            InlineKeyboardButton("🏠 Main menu", callback_data="menu:main"))

        message = "Select the airdrop you want to edit:"
        await self.bot.send_message(chat_id=telegram_id, text=message, reply_markup=keyboard)

    def load_tips(self, file_path=None):
        if file_path is None:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_file_dir)
            file_path = os.path.join(parent_dir, "resources/tips.txt")

        with open(file_path, "r", encoding="utf-8") as tips_file:
            tips_content = tips_file.read()

        return tips_content

    async def stop(self):
        await self.bot.close()
