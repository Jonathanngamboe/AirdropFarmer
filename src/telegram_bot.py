# telegram_bot.py
import asyncio
from collections import defaultdict
from aiogram.utils import executor
from aiogram import Bot, Dispatcher, types
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
import re

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token, db_manager):
        self.bot = Bot(token=token)
        self.db_manager = db_manager
        self.dp = Dispatcher(self.bot)
        self.register_handlers()
        self.started_users = set() # Used to keep track of the users that have started the bot
        self.farming_users = {} # Used to keep track of the users that are farming
        self.user_airdrop_executions = defaultdict(dict)
        self.airdrop_events = defaultdict(asyncio.Event)
        self.discord_handler = DiscordHandler(self.airdrop_events)
        self.register_handlers()
        self.welcome_text = None

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_add_wallet, Command("add_wallet"), content_types=types.ContentTypes.TEXT)
        self.dp.register_callback_query_handler(self.on_menu_button_click)

    async def get_user(self, telegram_id, username=None):
        user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)
        if user is None:
            user = await User.create_user(telegram_id, username, self.db_manager)
        return user

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name
        user = await self.get_user(telegram_id, username) # Get the user from the database and create a new one if it doesn't exist

        # Add user to the started_users set
        self.started_users.add(message.from_user.id)

        self.welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n📚 Detailed Guide: Guide\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"

        await self.send_menu(message.chat.id, 'main', message=self.welcome_text) # Send the main menu

    async def on_menu_button_click(self, query: CallbackQuery):
        if not await self.validate_user(query.from_user.id):
            return
        data = query.data.split(':')
        action = data[0]
        sub_data = data[1] if len(data) > 1 else None
        if action == 'menu':
            if sub_data == 'main':
                username = query.from_user.full_name
                await self.send_menu(query.from_user.id, sub_data, message=self.welcome_text,
                                     message_id=query.message.message_id)
            elif sub_data == 'add_wallet':
                await self.display_wallet_warning(query.message)  # Display the warning message before adding a wallet
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
        # Add more actions as needed

        await query.answer()

    async def send_menu(self, chat_id, menu, message="Choose an option:",message_id=None):
        user = await self.get_user(chat_id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []
        user_wallets = await user.get_wallets(self.db_manager) if await user.get_wallets(self.db_manager) else []
        keyboard = InlineKeyboardMarkup(row_width=2)
        if menu == 'main':
            keyboard.add(
                InlineKeyboardButton("💸 Manage airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("👛 Manage wallets", callback_data="menu:manage_wallets"),
                InlineKeyboardButton("💳 Subscription", callback_data="menu:manage_subscription"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
                InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"),
            )
        elif menu == 'manage_airdrops':
            # Create a temporary instance to get the active airdrops
            temp_airdrop_execution = AirdropExecution(None, None)
            available_airdrops = temp_airdrop_execution.get_active_airdrops()
            available_airdrop_names = [airdrop["name"] for airdrop in available_airdrops]
            # Remove user airdrops that are no longer active from the database
            for airdrop in user_airdrops:
                if airdrop not in available_airdrop_names:
                    await user.remove_airdrop(airdrop, self.db_manager)

            keyboard.add(
                InlineKeyboardButton("➕ Add new airdrop", callback_data="menu:add_airdrop"),
                InlineKeyboardButton("✏️ Edit my airdrops", callback_data="menu:edit_airdrops"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'add_airdrop':
            # Create a temporary instance to get the active airdrops
            temp_airdrop_execution = AirdropExecution(None, None)
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
                InlineKeyboardButton("➕ Add wallet", callback_data="menu:add_wallet"),
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

    async def update_keyboard_layout(self, chat_id, message_id, menu='main'):
        user_id = chat_id  # Assuming the chat_id corresponds to the user_id in this case
        if menu == 'main':
            keyboard = types.InlineKeyboardMarkup()
            if user_id in self.farming_users.keys():
                keyboard.add(types.InlineKeyboardButton(" 🛑 Stop farming", callback_data="stop_farming"))
            else:
                keyboard.add(types.InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"))

            await self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)

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

    async def validate_user(self, user_id: int) -> bool:
        if user_id in self.started_users:
            return True
        else:
            await self.bot.send_message(chat_id=user_id, text="Please run the /start command first.")
            return False

    async def cmd_start_farming(self, user_id, chat_id, message_id):
        user = await self.get_user(user_id)
        user_airdrops = await user.get_airdrops(self.db_manager) if await user.get_airdrops(self.db_manager) else []
        user_wallets = await user.get_wallets(self.db_manager)

        if user_id in self.farming_users.keys():
            await self.bot.send_message(chat_id,"Airdrop farming is already in progress. Please wait or press the 'Stop farming' button to stop.")
            return

        if not user_airdrops:
            await self.bot.send_message(chat_id, "You must have at least one airdrop registered to start farming.")
            return

        if not user_wallets:
            await self.bot.send_message(chat_id, "You must have at least one wallet registered to start farming.")
            return

        # Create a new AirdropExecution instance for the user
        logger = Logger(user_id, settings.LOG_PATH)
        airdrop_execution = AirdropExecution(self.discord_handler, logger)
        active_airdrops = airdrop_execution.get_active_airdrops()

        # Check if user_airdrops are among active_airdrops
        active_airdrop_names = [airdrop["name"] for airdrop in active_airdrops]
        valid_airdrops = [airdrop for airdrop in user_airdrops if airdrop in active_airdrop_names]
        if not valid_airdrops:
            await self.bot.send_message(chat_id, "You must have at least one active airdrop registered to start farming.")
            return

        self.farming_users[user_id] = True  # Add the user to the list of started users
        await self.bot.send_message(chat_id, "Airdrop farming started.")  # Notify the user about the airdrop farming start

        # Update the keyboard layout with the "Stop farming" button
        await self.update_keyboard_layout(user_id, message_id, menu='main')

        airdrop_execution.airdrops_to_execute = valid_airdrops  # Get the valid airdrops from the user

        # Call the airdrop_execution method in a separate asynchronous task
        airdrop_execution_task = asyncio.create_task(airdrop_execution.airdrop_execution())
        self.user_airdrop_executions[user_id] = (airdrop_execution, airdrop_execution_task)

        asyncio.create_task(
            self.notify_airdrop_execution(user_id))  # Notify the user about the airdrop execution status

    async def cmd_stop_farming(self, user_id, chat_id, message_id):
        if user_id in self.farming_users.keys():  # Check if the user is farming
            if user_id in self.user_airdrop_executions:
                airdrop_execution, airdrop_execution_task = self.user_airdrop_executions[user_id]
                airdrop_execution.stop_requested = True  # Stop the airdrop farming
                del self.farming_users[user_id]
                await self.bot.send_message(chat_id, "Stopping airdrop farming. Please wait...")
                await self.update_keyboard_layout(chat_id, message_id)
                await self.send_menu(chat_id, 'main', message=self.welcome_text)  # Send the main menu

                # Use asyncio.gather() to wait for the airdrop_execution_task to complete
                await asyncio.gather(airdrop_execution_task)
            else:
                await self.bot.send_message(chat_id, "Airdrop farming is not running.")
        else:
            await self.bot.send_message(chat_id, "Airdrop farming is not running.")
            return

    async def notify_airdrop_execution(self, user_id):
        # Verify if the airdrop execution has finished and notify the user
        while not self.user_airdrop_executions[user_id][
            0].finished:  # Access the 'finished' attribute from the airdrop_execution object
            await asyncio.sleep(1)

        user = await self.get_user(user_id)
        airdrop_results = self.user_airdrop_executions[user_id][0].airdrop_statuses

        for airdrop_name, status in airdrop_results.items():
            if status:
                await self.bot.send_message(user.telegram_id, f"Airdrop '{airdrop_name}' executed successfully. Check the logs for more details.")
            else:
                await self.bot.send_message(user.telegram_id, f"Error executing airdrop '{airdrop_name}'. Check the logs for more details.")

        # Message to inform the user that the farming has stopped completely
        if self.user_airdrop_executions[user_id][0].stop_requested:
            await self.bot.send_message(user.telegram_id, "Airdrop farming has been successfully stopped.")

        del self.user_airdrop_executions[user_id]
        del self.farming_users[user_id]
        await self.send_menu(user_id, 'main', message=self.welcome_text)  # Send the main menu

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
            InlineKeyboardButton("✅ Add airdrop", callback_data=f"add_airdrop:{airdrop_name}"),
            InlineKeyboardButton("🔙 Back to list", callback_data="menu:add_airdrop"),
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
        if not await self.validate_user(message.from_user.id): # Check if the user is registered
            return
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
                        f"Invalid wallet name. Please use only alphanumeric characters and underscores, with a maximum length of {settings.MAX_WALLET_NAME_LENGTH} characters and without spaces. Type /add_wallet to try again.")
                    await message.delete()  # Delete the message containing the private key for security reasons
                    return
            else:
                # Handle the case where the input format is incorrect
                await message.reply("Please provide the wallet information in the format wallet_name:private_key")
                await message.delete()  # Delete the message containing the private key for security reasons
                return
        else:
            # Handle the case where nothing is provided after the command add_wallet
            await message.reply("Please provide a wallet name and private key after the command. Type /add_wallet to try again.")
            return

        wallet = await self.check_private_key(private_key)
        if not wallet: # If the private key is invalid
            await message.reply("Invalid private key. Please try again. Type /add_wallet to try again.")
            return

        # Check if the wallet name is already in use
        if any(w['name'] == wallet_name for w in user_wallets):
            await message.reply("The wallet name is already in use. Please choose a different name. Type /add_wallet to try again.")
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

    async def stop(self):
        await self.bot.close()
