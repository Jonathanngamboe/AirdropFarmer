# telegram_bot.py

from aiogram.utils import executor
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ParseMode
from config import settings
import logging
from ecdsa import SECP256k1
from eth_keys import keys
from src.user import User
import re

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token, db_manager):
        self.bot = Bot(token=token)
        self.db_manager = db_manager
        self.dp = Dispatcher(self.bot)
        self.register_handlers()
        self.started_users = set()
        self.user = None

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_add_wallet, Command("add_wallet"), content_types=types.ContentTypes.TEXT)
        self.dp.register_callback_query_handler(self.on_menu_button_click)

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name

        self.user = await User.get_user_by_telegram_id(telegram_id, self.db_manager)
        if self.user is None:
            self.user = await User.create_user(telegram_id, username, self.db_manager)

        # Add user to the started_users set
        self.started_users.add(message.from_user.id)

        welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n📚 Detailed Guide: Guide\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"

        await self.send_menu(message.chat.id, 'main', message=welcome_text) # Send the main menu

    async def on_menu_button_click(self, query: CallbackQuery):
        if not await self.validate_user(query.from_user.id):
            return
        data = query.data.split(':')
        action = data[0]
        sub_data = data[1] if len(data) > 1 else None
        if action == 'menu':
            if sub_data == 'main':
                username = query.from_user.full_name
                welcome_text = f"🤖 Hey {username}, welcome on board!\n\nHow to use the bot?\n📚 Detailed Guide: Guide\n\n📩 If you have any questions, suggestions, or need assistance, please contact our support team at @support. We're always here to help!"
                await self.send_menu(query.from_user.id, sub_data, message=welcome_text, message_id=query.message.message_id)
            elif sub_data == 'add_wallet':
                await self.display_wallet_warning(query.message)  # Display the warning message before adding a wallet
            else:
                await self.send_menu(query.from_user.id, sub_data, message_id=query.message.message_id)
        elif action == 'add_airdrop':
            await self.cmd_add_airdrop(query) # Handle the add_airdrop action
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
                InlineKeyboardButton("✏️ Edit my airdrops", callback_data="menu:edit_airdrops"),
                InlineKeyboardButton("🔙 Back to main menu", callback_data="menu:main")
            )
        elif menu == 'add_airdrop':
            available_airdrops = ["Base", "Scroll", "Arbitrum", "Zksync", "Linear"]
            if self.user.airdrops:
                available_airdrops = list(set(available_airdrops) - set(self.user.airdrops))

            if available_airdrops:
                for airdrop in available_airdrops:
                    keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"show_airdrop:{airdrop}"))
                message = "Select the airdrop you want to farm:"
            else:
                message = "There are currently no additional airdrops to farm. Check your airdrops list to see which airdrops you are farming."
            keyboard.add(
                InlineKeyboardButton("🔙 Back to manage airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("🏠 Main menu", callback_data="menu:main")
            )
        elif menu == 'edit_airdrops':
            user_airdrops = self.user.airdrops if self.user.airdrops else []
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
            user_wallets = self.user.wallets if self.user.wallets else []

            if user_wallets:
                if len(self.user.wallets) > 1:
                    message = "Your wallets (click on a wallet to remove it):"
                else:
                    message = "Your wallet (click on the wallet to remove it):"
            else:
                message = "You don't have any wallets yet. Add a wallet to start farming."
            keyboard = InlineKeyboardMarkup(row_width=1)

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

    async def start_polling(self):
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

    async def validate_user(self, user_id: int) -> bool:
        if user_id in self.started_users:
            return True
        else:
            await self.bot.send_message(chat_id=user_id, text="Please run the /start command first.")
            return False

    async def cmd_start_farming(self, message: types.Message):
        print("Start farming")
        pass

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

        if airdrop_name:

            if not self.user.airdrops:
                self.user.airdrops = []

            self.user.airdrops.append(airdrop_name)
            await self.user.update_airdrops(self.db_manager)

            message = f"{airdrop_name} airdrop added to your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_menu(query.from_user.id, 'add_airdrop', message="Select the airdrop you want to farm:")

    async def cmd_remove_airdrop(self, query: CallbackQuery, airdrop_name: str):
        if self.user.airdrops and airdrop_name in self.user.airdrops:
            self.user.airdrops.remove(airdrop_name)
            await self.user.update_airdrops(self.db_manager)

            message = f"{airdrop_name} airdrop removed from your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_airdrop_edit_menu(query.from_user.id)
        else:
            message = f"{airdrop_name} airdrop not found in your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)

    async def cmd_add_wallet(self, message: types.Message):
        if not await self.validate_user(message.from_user.id):
            return
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
                        f"Invalid wallet name. Please use only alphanumeric characters and underscores, with a maximum length of {settings.MAX_WALLET_NAME_LENGTH} characters. Type /add_wallet to try again.")
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
        if any(w['name'] == wallet_name for w in self.user.wallets):
            await message.reply("The wallet name is already in use. Please choose a different name. Type /add_wallet to try again.")
            await message.delete()  # Delete the message containing the private key for security reasons
            return

        # Store the encrypted private key and wallet name in the user's database
        wallet['name'] = wallet_name

        # Store the encrypted private key in the user's database
        if wallet not in self.user.wallets:
            self.user.add_wallet(wallet)
            # Send a confirmation message
            await message.reply("Wallet added successfully!", parse_mode=ParseMode.HTML)
        else:
            await message.reply("This wallet is already added.")

        await message.delete() # Delete the message containing the private key for security reasons

        await self.send_menu(message.from_user.id, 'manage_wallets')

    async def is_valid_private_key(self, private_key_hex):
        private_key_int = int(private_key_hex, 16)
        return 0 < private_key_int < SECP256k1.order

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

    async def cmd_remove_wallet(self, query: CallbackQuery, wallet_name):
        wallet = next((wallet for wallet in self.user.wallets if wallet['name'] == wallet_name), None)
        if wallet in self.user.wallets:
            self.user.remove_wallet(wallet)
            message = f"Wallet {wallet['name']} removed successfully!"
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_menu(query.from_user.id, 'manage_wallets')
        else:
            message = f"Wallet {wallet_name} not found in your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)

    async def cmd_edit_wallets(self, query: CallbackQuery):
        # Implement the logic for editing the wallet list
        pass

    async def send_airdrop_edit_menu(self, telegram_id):
        keyboard = InlineKeyboardMarkup(row_width=1)

        if self.user.airdrops:
            for airdrop in self.user.airdrops:
                keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"edit_airdrop:{airdrop}"))
        else:
            message = "You don't have any airdrops in your list."
            await self.bot.send_message(chat_id=telegram_id, text=message)
            return

        keyboard.add(
            InlineKeyboardButton("🔙 Back to manage airdrops", callback_data="menu:manage_airdrops"),
            InlineKeyboardButton("🏠 Main menu", callback_data="menu:main"))

        message = "Select the airdrop you want to edit:"
        await self.bot.send_message(chat_id=telegram_id, text=message, reply_markup=keyboard)

    async def stop(self):
        await self.bot.close()
