# user.py
import json
import logging
import hvac
from config import settings
from src.secret_manager import SecretsManager


class User:
    def __init__(self, telegram_id, username, subscription_level, logger, airdrops=None,
                 twitter_credentials=None, discord_credentials=None, session_logs=None, subscription_expiry=None):
        self.telegram_id = telegram_id
        self.username = username
        self.subscription_level = subscription_level
        self.airdrops = airdrops if airdrops is not None else []
        self.twitter_credentials = twitter_credentials
        self.discord_credentials = discord_credentials
        self.session_logs = session_logs if session_logs is not None else []
        self.subscription_expiry = subscription_expiry
        self.sys_logger = logger
        self.sys_logger.add_log(f"Vault URL: {settings.VAULT_URL}", logging.INFO)
        self.sys_logger.add_log(f"Vault Token: {settings.VAULT_TOKEN}", logging.INFO)
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
        self.sys_logger.add_log(f"Removing wallet {wallet} for user {self.telegram_id}")
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
    async def create_user(cls, telegram_id, username, db_manager, logger):
        # save logger in the user object
        cls.logger = logger
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'subscription_level': 'Explorer (Free Plan)',
        }
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
