# telegram_bot.py
import asyncio
import json
import os
from collections import defaultdict
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
from coinpayments import CoinPaymentsAPI
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class TelegramBot:
    def __init__(self, token, db_manager, system_logger):
        self.bot = Bot(token=token)
        self.db_manager = db_manager
        self.dp = Dispatcher(self.bot)
        self.register_handlers()
        self.farming_users = {}  # Used to keep track of the users that are farming
        self.user_airdrop_executions = defaultdict(dict)
        self.airdrop_events = defaultdict(asyncio.Event)
        self.discord_handler = DiscordHandler(self.airdrop_events)
        self.user_loggers = {}  # Used to store Logger instances for each user
        self.register_handlers()
        self.welcome_text = "*How to use the bot?*\n\n📚 Detailed Guide: https://defi-bots.gitbook.io/airdrop-farmer/\n\n📤 If you have any questions, suggestions, or need assistance, please type /contact to reach us. We're always here to help!"
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5
        self.contact_text = "If you need help using the bot, please visit our wiki:\n\nhttps://defi-bots.gitbook.io/airdrop-farmer/\n\n📤 If you have a specific question or want to discuss your suscription plan, click the button below."
        self.cp = CoinPaymentsAPI(public_key=settings.COINPAYMENTS_PUBLIC_KEY, private_key=settings.COINPAYMENTS_PRIVATE_KEY)
        self.sys_logger = system_logger

    def register_handlers(self):
        self.dp.register_message_handler(self.cmd_start, Command(["start", "help"]))
        self.dp.register_message_handler(self.cmd_show_main_menu, Command(["menu"]))
        self.dp.register_message_handler(self.cmd_stop, commands=['stop'], commands_prefix='/', state='*')
        self.dp.register_message_handler(self.cmd_contact, commands=['contact'], commands_prefix='/', state='*')
        self.dp.register_message_handler(self.cmd_add_wallet, Command("add_wallet"), content_types=types.ContentTypes.TEXT)
        self.dp.register_message_handler(self.cmd_show_subscriptions_plans, commands=['subscription'], commands_prefix='/', state='*')
        self.dp.register_callback_query_handler(self.on_menu_button_click)

    async def start_polling(self):
        async def on_startup(dp):
            # Set bot commands in the chat menu
            bot_commands = [
                types.BotCommand(command="menu", description="Show the main menu"),
                types.BotCommand(command="subscription", description="Show subscription plans"),
                types.BotCommand(command="add_wallet", description="Add a wallet"),
                types.BotCommand(command="help", description="Show help"),
                types.BotCommand(command="contact", description="Contact support"),
            ]
            await self.bot.set_my_commands(bot_commands)

        async def on_shutdown(dp):
            # Remove webhook (if set)
            await self.bot.delete_webhook()

            # Close db connection (if used)
            await dp.storage.close()
            await dp.storage.wait_closed()

        # Schedule on_startup and on_shutdown coroutines
        loop = asyncio.get_running_loop()
        loop.create_task(on_startup(self.dp))

        try:
            await self.dp.start_polling()
        finally:
            await on_shutdown(self.dp)

    async def get_user(self, telegram_id, username=None):
        user = await User.get_user_by_telegram_id(telegram_id, self.db_manager, self.sys_logger)
        if user is None:
            user = await User.create_user(telegram_id, username, self.db_manager, self.sys_logger)
            user.sysl_logger = self.sys_logger
        return user

    async def cmd_start(self, message: types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.full_name

        user_logger = self.get_user_logger(
            telegram_id)  # This will create the logger instance for the user if it doesn't already exist
        user_logger.add_log(f"User {username} (ID: {telegram_id}) started the bot.")

        self.welcome_text = f"🤖 Hey {username}, welcome on board!\n\n*How to use the bot?*\n\n📚 Detailed Guide: https://defi-bots.gitbook.io/airdrop-farmer/\n\n📤 If you have any questions, suggestions, or need assistance, please type /contact to reach us. We're always here to help!"

        await self.send_menu(message.chat.id, 'main', message=self.welcome_text,
                             parse_mode='Markdown')  # Send the main menu

    async def cmd_stop(self, message: types.Message):
        user_id = message.from_user.id
        await self.bot.send_message(user_id,
                                    "Goodbye! The bot has been stopped. If you want to start again, just type /start")
        # Delete all the messages

    async def cmd_contact(self, message: types.Message = None, user_id: int = None, message_id=None):
        if user_id is None:
            user_id = message.from_user.id

        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Back", callback_data="menu:main"),
            InlineKeyboardButton("💬 Write us here", callback_data="contact_us")
        )
        if message_id:
            await self.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=self.contact_text,
                                             reply_markup=keyboard)
        else:
            await self.bot.send_message(user_id, self.contact_text, reply_markup=keyboard)

    async def cmd_send_contact_message(self, message: types.Message):
        user_id = message.from_user.id
        admin_id = settings.ADMIN_TELEGRAM_ID
        user_message = message.text
        if user_message.lower() == "cancel":
            await self.bot.send_message(user_id, "Contact request canceled.")
        else:
            await self.bot.send_message(admin_id,
                                        f"Message from @{message.from_user.username} (ID: {user_id}): {user_message}")
            await self.bot.send_message(user_id,
                                        "Your message has been sent to our support team. We will get back to you as soon as possible.")
        await self.send_menu(user_id, 'main', message=self.welcome_text, parse_mode='Markdown')

    async def cmd_show_subscriptions_plans(self, message: types.Message = None, user_id: int = None, message_id=None):
        if user_id is None:
            user_id = message.from_user.id
        message_text = "🚀 *Airdrop Farmer Subscription Plans*\n\n"
        # Current user subscription
        user = await self.get_user(user_id)
        current_plan_index = 0
        if user.subscription_level is not None:
            message_text += f"🔸 *Current Plan*: {user.subscription_level}\n\n"
            current_plan_index = next(
                (i for i, plan in enumerate(settings.SUBSCRIPTION_PLANS) if plan['level'] == user.subscription_level),
                0)
            # Show the expiry date
            if user.subscription_expiry is not None:
                message_text += f"🔸 *Expiry Date*: {user.subscription_expiry.strftime('%d %b %Y')}\n\n"

        # Available plans
        for plan in settings.SUBSCRIPTION_PLANS:
            message_text += f"🔹 *{plan['level']}*\n"
            if isinstance(plan['price_monthly'], (int, float)):
                message_text += f"Price (Monthly): ${plan['price_monthly']}"
                if plan['price_monthly'] != 0:
                    message_text += " (Excl. fees)\n"
                else:
                    message_text += "\n"
            else:
                message_text += f"Price: {plan['price_monthly']}\n"
            message_text += f"Wallets: {plan['wallets']}\n"
            message_text += f"Max. Airdrops: {plan['airdrop_limit']}\n"
            message_text += "Features:\n"
            for feature in plan['features']:
                message_text += f"  • {feature}\n"
            if plan.get('most_popular'):
                message_text += "💥 *Most Popular*\n"
            message_text += "\n"

        message_text += "Choose a plan to subscribe to:"

        keyboard = InlineKeyboardMarkup()
        for i, plan in enumerate(settings.SUBSCRIPTION_PLANS[current_plan_index:]):
            if i >= current_plan_index and i != 0: # Only show the plans after the current one and not the first one (free plan)
                keyboard.add(InlineKeyboardButton(f"{plan['level'].split('(', 1)[0].strip()}", callback_data=f"menu:choose_subscription_type:{plan['level']}"))

        keyboard.add(InlineKeyboardButton("🔙 Back to menu", callback_data="menu:main"))

        if message_id:
            await self.bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode=types.ParseMode.MARKDOWN
            )
        else:
            await self.bot.send_message(
                user_id,
                message_text,
                reply_markup=keyboard,
                parse_mode=types.ParseMode.MARKDOWN
            )

    async def choose_subscription_type(self, user_id, message_id, plan):
        message_text = f"Select the subscription type for the *{plan}* plan:"
        buttons_row1 = [
            {"text": "📅 Monthly", "callback_data": f"menu:choose_currency:{plan}:monthly"},
            {"text": "📆 Annual", "callback_data": f"menu:choose_currency:{plan}:annual"},
        ]
        buttons_row2 = [
            {"text": "🔙 Back", "callback_data": "menu:manage_subscription"},
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons_row1, buttons_row2])
        await self.bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN,
        )

    async def choose_currency(self, user_id, message_id, duration, plan):
        message_text = f"Select the currency for the *{plan}* ({duration}) plan:"

        # Get available coins
        coins = await self.get_available_coins()

        # Remove duplicate coin names
        unique_coins = {}
        for coin_code in coins:
            name = coin_code.split('.')[0]
            if name not in unique_coins:
                unique_coins[name] = coin_code

        # Generate the inline keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        for coin in unique_coins:
            keyboard.add(InlineKeyboardButton(f"{coin}", callback_data=f"menu:choose_network:{plan}:{duration}:{coin}"))

        keyboard.add(InlineKeyboardButton("🔙 Back", callback_data=f"menu:choose_subscription_type:{plan}"))

        if message_id:
            await self.bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode=types.ParseMode.MARKDOWN
            )
        else:
            await self.bot.send_message(
                user_id,
                message_text,
                reply_markup=keyboard,
                parse_mode=types.ParseMode.MARKDOWN
            )

    async def choose_network(self, user_id, message_id, plan, duration, coin_name):
        message_text = f"Choose the network for {coin_name}:"
        # TODO: Only add networks that will avoid the error "Amount too small, there would be nothing left!" due to transaction fees
        # TODO: Retrieve the full token name directly to avoid calling the Coinpayment API twice in a row
        # Get available coins
        coins = await self.get_available_coins()

        # Filter coins by the selected coin name
        selected_coins = {coin_code: coin_data for coin_code, coin_data in coins.items() if
                          coin_code.split('.')[0] == coin_name}

        # Generate the inline keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        for code, data in selected_coins.items():
            token, network = (code.split('.') + [None])[:2]

            if network is not None:
                if token == 'BNB' and network == 'BSC':
                    network_to_show = 'BEP20'
                else:
                    network_to_show = network
            elif token == 'USDC' or token == 'ETH':
                network_to_show = 'ERC20'
            else:
                network_to_show = token

            keyboard.add(InlineKeyboardButton(f"{network_to_show}", callback_data=f"send_transaction_details:{plan}:{duration[0]}:{code}"))

        keyboard.add(InlineKeyboardButton("🔙 Back", callback_data=f"menu:choose_currency:{plan}:{duration}"))

        await self.bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )

    async def send_transaction_details(self, user_id, chosen_plan, duration, chosen_coin):
        user = await self.get_user(user_id)

        if duration == 'm':  # Monthly
            duration = '1 month'
            duration_days = 30
            price_key = 'price_monthly'
        else:
            duration = '1 year'
            duration_days = 365
            price_key = 'price_yearly'

        # Get the subscription plan details
        plan_details = next((p for p in settings.SUBSCRIPTION_PLANS if
                             p['level'].split('(', 1)[0].strip() == chosen_plan.split('(', 1)[0].strip()), None)
        if not plan_details or plan_details.get(price_key) is None:
            self.bot.send_message(user_id, "Invalid subscription plan. Go back and try again.")
            return None

        # Calculate the price and discount for subscription upgrade
        discount = 0
        if user.subscription_level == chosen_plan:
            # Extend the current subscription
            remaining_days = (user.subscription_expiry - datetime.now()).days
            duration_days += remaining_days
        elif user.subscription_level is not None and user.subscription_expiry is not None:
            # Upgrade to a more expensive subscription
            current_plan = next((p for p in settings.SUBSCRIPTION_PLANS if p['level'] == user.subscription_level), None)
            remaining_days = (user.subscription_expiry - datetime.now()).days

            old_daily_rate = current_plan[price_key] / duration_days
            remaining_value = remaining_days * old_daily_rate

            new_daily_rate = plan_details[price_key] / duration_days
            new_remaining_value = remaining_days * new_daily_rate

            discount = remaining_value - new_remaining_value if new_remaining_value > remaining_value else 0

        plan_details['currency'] = chosen_coin
        plan_details['price_with_discount'] = plan_details[price_key] - discount

        # Create a CoinPayments transaction
        response = self.cp.create_transaction(amount=float(plan_details['price_with_discount']),
                                              currency1='USD',
                                              currency2=plan_details['currency'],
                                              buyer_email=settings.ADMIN_EMAIL,
                                              item_name=plan_details['level'],
                                              ipn_url=settings.COINPAYMENTS_IPN_URL,
                                              )
        if response and response['error'] != 'ok':
            self.sys_logger.add_log(f'CoinPayments error: {response["error"]}', logging.ERROR)

            try:
                await self.bot.answer_callback_query(user_id, response['error'], show_alert=True)
            except:
                await self.bot.send_message(user_id, response['error'])
            return None

        if response and response['error'] == 'ok':
            transaction_id = response['result']['txn_id']

            # Send the payment details to the user and if the user has a discount, show it
            payment_details = (
                "💵 *Subscription Payment*\n\n"
                "• User ID: `{}`\n"
                "• Plan: `{}`\n"
                "• Duration: `{}`\n"
                "• Amount: `{}` {}\n"
                "{}"
                "• Transaction ID: `{}`\n"
                "• Payment Address: `{}`\n\n"
                "Please send the exact amount to the provided address and wait for the confirmation. "
                "Your subscription will be activated once the payment is confirmed."
            ).format(
                user_id,
                plan_details['level'],
                duration,
                response['result']['amount'],
                plan_details['currency'],
                "• Discount: `{}` {}\n• Total: `{}` {}\n".format(discount, plan_details['currency'],
                                                                 response['result']['amount'] - discount,
                                                                 plan_details['currency']) if discount > 0 else "",
                transaction_id,
                response['result']['address']
            )

            # Save the transaction details to the database
            try:
                await self.db_manager.save_transaction_details(user_id, transaction_id, json.dumps(response['result']))
                await self.bot.send_message(user_id, payment_details, parse_mode='Markdown')
            except Exception as e:
                self.sys_logger.add_log(f"Error saving transaction details: {e}", logging.ERROR)
                return None
            return transaction_id
        else:
            self.sys_logger.add_log(f"Error creating transaction: {response['error']}", logging.ERROR)
            return None

    async def get_available_coins(self):
        accepted_coins = {}
        coins_response = self.cp.rates(short=1, accepted=2)
        # TODO: make this method faster by directly catching accepted coins
        if coins_response['error'] == 'ok':
            for coin, coin_data in coins_response["result"].items():
                if coin_data["accepted"] == 1:
                    accepted_coins[coin] = coin_data
            return accepted_coins
        else:
            return None

    async def on_menu_button_click(self, query: CallbackQuery):
        data = query.data.split(':')
        action = data[0]
        params = data[1:]

        if action == 'menu':
            if params[0] == 'main':
                await self.send_menu(query.from_user.id, params[0], message=self.welcome_text,
                                     message_id=query.message.message_id, parse_mode='Markdown')
            elif params[0] == 'add_wallet':
                await self.display_wallet_warning(query.message)
            elif params[0] == 'show_logs':
                await self.send_menu(query.from_user.id, params[0], message_id=query.message.message_id)
            elif params[0] == 'contact':
                await self.cmd_contact(user_id=query.from_user.id, message_id=query.message.message_id)
            elif params[0] == 'manage_subscription':
                await self.cmd_show_subscriptions_plans(user_id=query.from_user.id, message_id=query.message.message_id)
            elif params[0] == 'choose_subscription_type':
                # Searches for plans that have "level" params[1] and price_monthly is of type str
                if next((p for p in settings.SUBSCRIPTION_PLANS if p['level'] == params[1] and isinstance(p['price_monthly'], (str))), None):
                    await self.cmd_contact(user_id=query.from_user.id, message_id=query.message.message_id)
                else:
                    await self.choose_subscription_type(user_id=query.from_user.id, message_id=query.message.message_id, plan=params[1])
            elif params[0] == 'choose_currency':
                await self.choose_currency(user_id=query.from_user.id, plan=params[1], duration=params[2], message_id=query.message.message_id)
            elif params[0] == 'choose_network':
                await self.choose_network(user_id=query.from_user.id, message_id=query.message.message_id, plan=params[1], duration=params[2], coin_name=params[3])

            else:
                await self.send_menu(query.from_user.id, params[0], message_id=query.message.message_id)
        elif action == 'add_airdrop':
            await self.cmd_add_airdrop(query)
        elif action == 'show_airdrop':
            await self.cmd_show_airdrop_details(query, airdrop_name=params[0])
        elif action == 'edit_airdrop':
            await self.cmd_edit_airdrop(query, airdrop_name=params[0])
        elif action == 'remove_airdrop':
            await self.cmd_remove_airdrop(query, params[0])
        elif action == 'remove_wallet':
            await self.cmd_remove_wallet(query, params[0])
        elif action == 'start_farming':
            await self.cmd_start_farming(query.from_user.id, query.message.chat.id, query.message.message_id)
        elif action == "stop_farming":
            await self.cmd_stop_farming(query.from_user.id, query.message.chat.id, query.message.message_id)
        elif action == "display_log":
            await self.cmd_display_log(query.from_user.id, query.message.chat.id, params[0], query.message.message_id)
        elif action == "contact_us":
            user_id = query.from_user.id
            await self.bot.send_message(user_id, "Please type your message in the chat or type 'cancel' to cancel:")
            self.dp.register_message_handler(self.cmd_send_contact_message, lambda msg: msg.from_user.id == user_id)
        elif action == "send_transaction_details":
            await self.send_transaction_details(query.from_user.id, chosen_plan=params[0], duration=params[1], chosen_coin=params[2])

        await self.retry_request(self.bot.answer_callback_query, query.id)

    async def retry_request(self, func, *args, **kwargs):
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                return await func(*args, **kwargs)
            except InvalidQueryID as e:
                self.sys_logger.add_log(f"WARNING - Query is too old or query ID is invalid: {e}", logging.WARNING)
                return None  # Stop retrying as this exception won't likely resolve on its own
            except Exception as e:
                retries += 1
                self.sys_logger.add_log(f"WARNING - Retrying request due to error: {e}", logging.WARNING)
                await asyncio.sleep(self.RETRY_DELAY)
        self.sys_logger.add_log(f"ERROR - Request failed after {self.MAX_RETRIES} retries.", logging.ERROR)
        return None

    async def cmd_show_main_menu(self, message: types.Message):
        await self.send_menu(message.chat.id, 'main', message=self.welcome_text,
                             parse_mode='Markdown')  # Send the main menu

    async def send_menu(self, chat_id, menu, message="Choose an option:", message_id=None, parse_mode=None):
        user = await self.get_user(chat_id)
        user_airdrops = await user.get_airdrops(self.db_manager)
        user_wallets = await user.get_wallets()
        keyboard = InlineKeyboardMarkup(row_width=2)
        if menu == 'main':
            keyboard.add(
                InlineKeyboardButton("💸 My airdrops", callback_data="menu:manage_airdrops"),
                InlineKeyboardButton("👛 My wallets", callback_data="menu:manage_wallets"),
                InlineKeyboardButton("📦 Subscription", callback_data="menu:manage_subscription"),
                InlineKeyboardButton("📋 Logs", callback_data="menu:show_logs"),
                InlineKeyboardButton("📤 Contact", callback_data="menu:contact"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
                InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"),
            )
        elif menu == 'manage_airdrops':
            # Get the active airdrops
            available_airdrops = AirdropExecution().get_active_airdrops()
            available_airdrop_names = [airdrop["name"] for airdrop in available_airdrops]
            # Remove user airdrops that are no longer active from the database
            for airdrop in user_airdrops:
                if airdrop not in available_airdrop_names:
                    await user.remove_airdrop(airdrop, self.db_manager)

            keyboard.add(
                InlineKeyboardButton("✏️ Edit my airdrops", callback_data="menu:edit_airdrops"),
                InlineKeyboardButton("➕ Add new airdrop", callback_data="menu:add_airdrop"),
                InlineKeyboardButton("🔙 Back to menu", callback_data="menu:main"),
            )
        elif menu == 'add_airdrop':
            # Create a temporary instance to get the active airdrops
            available_airdrops = AirdropExecution().get_active_airdrops()

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
                InlineKeyboardButton("🔙 Back", callback_data="menu:manage_airdrops"),
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
                InlineKeyboardButton("🔙 Back", callback_data="menu:manage_airdrops"),
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
                InlineKeyboardButton("🔙 Back to menu", callback_data="menu:main"),
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

            keyboard.add(InlineKeyboardButton("🔙 Back to menu", callback_data="menu:main"))

            message = "Select a date to view the logs:"
        elif menu == 'manage_subscription':
            await self.cmd_show_subscriptions_plans(user_id=chat_id)
        elif menu == 'choose_currency':
            await self.choose_currency(user_id=chat_id, message_id=message_id)
        elif menu == 'settings':
            keyboard.add(
                InlineKeyboardButton("🔙 Back to menu", callback_data="menu:main")
            )
        # Add more menus as needed
        else:
            return

        if message_id:
            await self.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"{message}",
                                             reply_markup=keyboard, parse_mode=parse_mode if parse_mode else None)
        else:
            await self.bot.send_message(chat_id=chat_id, text=f"{message}", reply_markup=keyboard,
                                        parse_mode=parse_mode if parse_mode else None)

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
        user_airdrops = await user.get_airdrops(self.db_manager)
        user_wallets = await user.get_wallets()

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
            await self.bot.send_message(chat_id,
                                        "You must have at least one active airdrop registered to start farming.")
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

    async def cmd_stop_farming(self, user_id, chat_id):
        if user_id in self.farming_users.keys():
            airdrop_execution, airdrop_execution_task = self.user_airdrop_executions.get(user_id, (None, None))
            if airdrop_execution:
                airdrop_execution.stop_requested = True
                self.get_user_logger(user_id).add_log("WARNING - Stop farming requested.")
                await self.bot.send_message(chat_id,
                                            "Stopping airdrop farming. This may take a few minutes. Please wait...")
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
        await self.send_menu(user_id, 'main', message=self.welcome_text, parse_mode='Markdown')

        del self.user_airdrop_executions[user_id]
        del self.farming_users[user_id]

    async def update_keyboard_layout(self, chat_id, menu='main'):
        user_id = chat_id  # Assuming the chat_id corresponds to the user_id in this case
        message_id = self.farming_users[user_id]['message_id']  # Get the old stored message_id
        if menu == 'main':
            keyboard = types.InlineKeyboardMarkup()
            if self.farming_users[user_id]['status']:  # If the user is farming, show the 'Stop farming' button
                keyboard.add(types.InlineKeyboardButton("🛑 Stop farming", callback_data="stop_farming"))
            else:
                keyboard.add(types.InlineKeyboardButton("🚀 Start farming", callback_data="start_farming"))

            try:
                await self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
            except MessageNotModified:
                self.sys_logger.add_log("WARNING - Message not modified: new keyboard layout is the same as the current one.")

    def get_user_logger(self, user_id):
        if user_id not in self.user_loggers:
            self.user_loggers[user_id] = Logger(user_id)
        return self.user_loggers[user_id]

    async def cmd_show_airdrop_details(self, query: CallbackQuery, airdrop_name: str):
        # Use AirdropExecution class to load active airdrops
        airdrops = AirdropExecution().get_active_airdrops()

        airdrop = next((a for a in airdrops if a["name"] == airdrop_name), None)

        if airdrop is not None:
            actions = airdrop["actions"]
            actions_text = []
            for action in actions:
                if action["isActivated"]:
                    action_text = f"🔸 <b>{action['platform'].capitalize()}:</b> {action['action'].replace('_', ' ').title()}"
                    if "blockchain" in action:
                        action_text += f" ({action['blockchain'].capitalize().replace('_', ' ')})\n"
                    action_details = []
                    if "contract_address" in action:
                        action_details.append(f"  - Contract address: {action['contract_address']}")
                    if "function_name" in action:
                        action_details.append(f"  - Function name: {action['function_name']}")
                    if "exchange_address" in action:
                        action_details.append(f"  - Exchange address: {action['exchange_address']}")
                    if "token_address" in action:
                        action_details.append(f"  - Token address: {action['token_address']}")
                    if "recipient_address" in action:
                        action_details.append(f"  - Recipient: {action['recipient_address']}")
                    if "msg_value" in action:
                        action_details.append(f"  - Value: {action['msg_value']} wei")
                    if "amount" in action:
                        action_details.append(f"  - Amount: {action['amount']} tokens")
                    if "amount_in_wei" in action:
                        action_details.append(f"  - Amount: {action['amount_in_wei']} wei")
                    if "slippage" in action:
                        action_details.append(f"  - Slippage tolerance: {action['slippage'] * 100}%")

                    action_text += "\n".join(action_details)
                    actions_text.append(action_text)

            description = f"<b>Airdrop:</b> {airdrop_name}\n\n<b>Actions:</b>\n" + "\n\n".join(actions_text)
        else:
            description = "Airdrop description not found."

        message = f"{description}\n\nDo you want to add this airdrop to your list?"

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🔙 Back", callback_data="menu:add_airdrop"),
            InlineKeyboardButton("✅ Add airdrop", callback_data=f"add_airdrop:{airdrop_name}"),
            InlineKeyboardButton("🏠 Main menu", callback_data="menu:main"),
        )

        await self.bot.edit_message_text(chat_id=query.from_user.id, message_id=query.message.message_id, text=message,
                                         reply_markup=keyboard, parse_mode='HTML')

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
            InlineKeyboardButton("🔙 Back", callback_data="menu:edit_airdrops")
        )

        await self.bot.edit_message_text(chat_id=query.from_user.id, message_id=query.message.message_id, text=message,
                                         reply_markup=keyboard)

    async def cmd_add_airdrop(self, query: CallbackQuery):
        data = query.data.split(':')
        airdrop_name = data[1] if len(data) > 1 else None

        user = await self.get_user(query.from_user.id)

        await user.add_airdrop(airdrop_name, self.db_manager)
        message = f"{airdrop_name} airdrop added to your list."
        await self.bot.send_message(chat_id=query.from_user.id, text=message)
        await self.send_menu(query.from_user.id, 'add_airdrop', message="Select the airdrop you want to farm:")

    async def cmd_remove_airdrop(self, query: CallbackQuery, airdrop_name: str):
        user = await self.get_user(query.from_user.id)
        user_airdrops = await user.get_airdrops(self.db_manager)
        # Check if airdrop to remove is in user's list
        if airdrop_name in user_airdrops:
            await user.remove_airdrop(airdrop_name, self.db_manager)
            message = f"{airdrop_name} airdrop removed from your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)
            await self.send_airdrop_edit_menu(query.from_user.id)
        else:
            message = f"{airdrop_name} airdrop not found in your list."
            await self.bot.send_message(chat_id=query.from_user.id, text=message)

    async def cmd_add_wallet(self, message: types.Message):
        user = await self.get_user(message.from_user.id)
        user_wallets = await user.get_wallets()
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
            await message.reply(
                "Please provide a wallet name folowed by a colon and your private key.\nType /add_wallet to try again.")
            return

        wallet = await self.check_private_key(private_key)
        if not wallet:  # If the private key is invalid
            await message.reply("Invalid private key. Please try again.\nType /add_wallet to try again.")
            return

        # Check if the wallet name is already in use
        if any(w['name'] == wallet_name for w in user_wallets):
            await message.reply(
                "The wallet name is already in use. Please choose a different name.\nType /add_wallet to try again.")
            await message.delete()  # Delete the message containing the private key for security reasons
            return

        # Store the encrypted private key and wallet name in the user's database
        formatted_wallet_name = f"{wallet_name} ({wallet['public_key'][:4]}...{wallet['public_key'][-4:]})"
        wallet['name'] = formatted_wallet_name

        # Store the private key in the user's database
        if wallet not in user_wallets:
            await user.add_wallet(wallet)
            # Send a confirmation message
            await message.reply("Wallet added successfully!", parse_mode=ParseMode.HTML)
        else:
            await message.reply("This wallet is already added.")

        await message.delete()  # Delete the message containing the private key for security reasons

        await self.send_menu(message.from_user.id, 'manage_wallets')

    async def cmd_remove_wallet(self, query: CallbackQuery, wallet_name):
        user = await self.get_user(query.from_user.id)
        user_wallets = await user.get_wallets()
        wallet = next((wallet for wallet in user_wallets if wallet['name'] == wallet_name), None)
        if wallet in user_wallets:
            await user.remove_wallet(wallet)
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
        user_airdrops = await user.get_airdrops(self.db_manager)

        if user_airdrops:
            for airdrop in user_airdrops:
                keyboard.add(InlineKeyboardButton(airdrop, callback_data=f"edit_airdrop:{airdrop}"))
        else:
            message = "Your airdrop list is empty."
            await self.bot.send_message(chat_id=telegram_id, text=message)
            await self.send_menu(telegram_id, 'manage_airdrops')
            return

        keyboard.add(
            InlineKeyboardButton("🔙 Back", callback_data="menu:manage_airdrops"),
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
