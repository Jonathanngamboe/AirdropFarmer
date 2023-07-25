# user.py
import json
import logging
import hvac
import shortuuid
import string
from config import settings
from src.secret_manager import SecretsManager
from datetime import datetime, timezone, timedelta

MAX_REFERRAL_CODE_USES = 5

class User:
    def __init__(self, telegram_id, username, subscription_level, logger, airdrops=None,
                 twitter_credentials=None, discord_credentials=None, session_logs=None, subscription_expiry=None, referral_code=None):
        self.telegram_id = telegram_id
        self.username = username
        self.subscription_level = subscription_level
        self.airdrops = airdrops if airdrops is not None else []
        self.twitter_credentials = twitter_credentials
        self.discord_credentials = discord_credentials
        self.session_logs = session_logs if session_logs is not None else []
        self.subscription_expiry = subscription_expiry
        self.referral_code = referral_code
        self.sys_logger = logger
        self._secrets_manager = SecretsManager(url=settings.VAULT_URL, token=settings.VAULT_TOKEN, logger=self.sys_logger)

    async def add_airdrop(self, airdrop, db_manager):
        existing_airdrops = await self.get_airdrops(db_manager)
        if airdrop not in existing_airdrops:
            self.airdrops.append(airdrop)
            airdrops_json = json.dumps(self.airdrops)  # Convert the list of airdrops to a json
            await db_manager.execute_query(
                "UPDATE users SET airdrops = $1 WHERE telegram_id = $2", airdrops_json, self.telegram_id
            )

    async def remove_airdrop(self, airdrop, db_manager):
        existing_airdrops = await self.get_airdrops(db_manager)
        if airdrop in existing_airdrops:
            self.airdrops.remove(airdrop)
            airdrops_json = json.dumps(self.airdrops)  # Convert the list of airdrops to a json
            await db_manager.execute_query(
                "UPDATE users SET airdrops = $1 WHERE telegram_id = $2", airdrops_json, self.telegram_id
            )

    async def get_airdrops(self, db_manager):
        results = await db_manager.fetch_query(
            "SELECT airdrops FROM users WHERE telegram_id = $1 AND airdrops IS NOT NULL", self.telegram_id
        )
        if results:
            airdrops = json.loads(results[0]['airdrops'])
            return airdrops if airdrops else []
        return []

    async def add_wallet(self, wallet):
        try:
            self._secrets_manager.store_wallet(self.telegram_id, wallet)
            return True
        except Exception as e:
            self.sys_logger.add_log(f"Error during wallet addition: {e}", logging.ERROR)
            return False

    async def remove_wallet(self, wallet):
        try:
            existing_wallets = await self.get_wallets()
            if wallet in existing_wallets:
                self._secrets_manager.delete_wallet(self.telegram_id, wallet)
                return True
            else:
                self.sys_logger.add_log(f"Wallet {wallet} not found for user {self.telegram_id}")
                return False
        except Exception as e:
            self.sys_logger.add_log(f"Error during wallet deletion: {e}", logging.ERROR)
            return False

    async def remove_all_wallets(self):
        try:
            existing_wallets = await self.get_wallets()
            if not existing_wallets:
                self.sys_logger.add_log(f"No wallets found for user {self.telegram_id}")
                return False
            else:
                for wallet in existing_wallets:
                    self._secrets_manager.delete_wallet(self.telegram_id, wallet)
                self.sys_logger.add_log(f"All wallets removed for user {self.telegram_id}")
                return True
        except Exception as e:
            self.sys_logger.add_log(f"Error during wallet deletion: {e}", logging.ERROR)
            return False

    async def get_wallets(self):
        try:
            # Add the user's wallets from secrets manager to the list of wallets
            wallets = self._secrets_manager.get_wallet(self.telegram_id)
            if wallets is None:
                return []
            return wallets
        except hvac.exceptions.InvalidPath:
            self.sys_logger.add_log(f"Error during wallet retrieval: No wallets found for user {self.telegram_id}")
            return []

    def set_twitter_credentials(self, twitter_credentials):
        self.twitter_credentials = twitter_credentials
        # Update the user's Twitter credentials in the database

    def set_discord_credentials(self, discord_credentials):
        self.discord_credentials = discord_credentials
        # Update the user's Discord credentials in the database

    async def update_subscription_level(self, subscription_level):
        self.subscription_level = subscription_level
        await self.db_manager.execute_query(
            "UPDATE users SET subscription_level=$1 WHERE telegram_id=$2",
            subscription_level,
            self.telegram_id,
        )

    def log_session(self, log_data):
        self.session_logs.append(log_data)
        # Update the user's session logs in the database

    def get_session_logs(self):
        # Retrieve the user's session logs from the database
        return self.session_logs

    def get_subscription_info(self):
        subscription_levels = settings.SUBSCRIPTION_LEVELS
        return subscription_levels[self.subscription_level]

    @classmethod
    async def create_user(cls, telegram_id, username, db_manager, logger, referral_code=None):
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'subscription_level': 'Explorer (Free Plan)',
            'logger': logger  # include the logger in the user_data dictionary
        }
        if referral_code:
            # If the referral_code is not None, add it to the user_data dictionary
            user_data['referral_code'] = referral_code
            # Update the referral code used times
            try:
                await db_manager.execute_query(
                    "UPDATE referral_codes SET used_times = used_times + 1 WHERE code_value = $1", referral_code)
                logger.add_log(f"Referral code {referral_code} used times updated successfully", logging.INFO)
            except Exception as e:
                logger.add_log(f"Error during updating referral code used times: {e}", logging.ERROR)
                raise e

        user = cls(**user_data)
        try:
            await db_manager.execute_query(
                "INSERT INTO users (telegram_id, username, subscription_level) VALUES ($1, $2, $3)", telegram_id,
                username, user_data['subscription_level'])
            logger.add_log(f"User {telegram_id} inserted successfully", logging.INFO)
        except Exception as e:
            logger.add_log(f"Error during user insertion: {e}", logging.ERROR)
            raise e
        return user

    async def generate_referral_code(self, db_manager):
        # Generate a unique referral code
        referral_code = shortuuid.ShortUUID().random(length=6)  # adjust length according to your requirement

        # Check if user has already generated a referral code today
        now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)
        existing_code = await db_manager.fetch_query(
            "SELECT code_value FROM referral_codes WHERE created_by = $1 AND created_at BETWEEN $2 AND $3",
            self.telegram_id, start_of_day, end_of_day
        )
        if existing_code:
            self.sys_logger.add_log(f"User {self.telegram_id} has already generated a referral code today")
            raise Exception("You can only generate one referral code per day")

        # Save referral code in database
        try:
            await db_manager.execute_query(
                "INSERT INTO referral_codes (code_value, created_by) VALUES ($1, $2)",
                referral_code, self.telegram_id
            )
            await db_manager.execute_query(
                "UPDATE users SET referral_code = $1 WHERE telegram_id = $2",
                referral_code, self.telegram_id
            )
            self.sys_logger.add_log(f"User {self.telegram_id} generated a new referral code")
            return referral_code
        except Exception as e:
            self.sys_logger.add_log(f"Error during referral code generation: {e}", logging.ERROR)
            raise e

    @staticmethod
    async def check_referral_code(referral_code, db_manager, logger):
        try:
            result = await db_manager.fetch_query(
                "SELECT * FROM referral_codes WHERE code_value = $1", referral_code
            )
            # If the referral code does not exist, return False
            if not result:
                return False

            # If the referral code exists but has been used 3 times or more, raise an exception
            if result[0]['used_times'] >= MAX_REFERRAL_CODE_USES:
                raise Exception(f"Referral code *{referral_code}* has already been used *{MAX_REFERRAL_CODE_USES}* times. Press /start to try again.")

            # If the referral code exists and has been used less than 3 times, return True
            return True
        except Exception as e:
            if str(e) == f"Referral code *{referral_code}* has already been used *{MAX_REFERRAL_CODE_USES}* times. Press /start to try again.":
                raise e
            else:
                return False

    @classmethod
    async def get_user_by_telegram_id(cls, telegram_id: int, db_manager, logger) -> "User":
        user_data = await db_manager.fetch_query(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )

        if user_data:
            record = user_data[0]
            user_data = dict(record)
            user_data.pop('id', None)
            user_data.pop('created_at', None)

            if user_data.get('airdrops'):
                user_data['airdrops'] = json.loads(user_data['airdrops'])
            else:
                user_data['airdrops'] = []


            user = cls(**user_data, logger=logger)
            return user
        return None
