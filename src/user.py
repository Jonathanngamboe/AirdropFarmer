# user.py
import json
import logging

from config import settings
from cryptography.fernet import Fernet

class User:
    def __init__(self, telegram_id, username, subscription_level, airdrops=None,
                 twitter_credentials=None, discord_credentials=None, session_logs=None,
                 encrypted_wallets=None, subscription_expiry=None):
        self.telegram_id = telegram_id
        self.username = username
        self.subscription_level = subscription_level
        self.airdrops = airdrops if airdrops is not None else []
        self.twitter_credentials = twitter_credentials
        self.discord_credentials = discord_credentials
        self.session_logs = session_logs if session_logs is not None else []
        self.encrypted_wallets = encrypted_wallets if encrypted_wallets is not None else []
        self.subscription_expiry = subscription_expiry

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

    async def add_wallet(self, wallet, db_manager):
        decrypted_wallets = await self.get_wallets(db_manager)

        if wallet not in decrypted_wallets:
            decrypted_wallets.append(wallet)
            fernet = Fernet(settings.ENCRYPTION_KEY)
            encrypted_wallets = fernet.encrypt(json.dumps(decrypted_wallets).encode()).decode()

            result = await db_manager.execute_query(
                "UPDATE users SET encrypted_wallets = $1 WHERE telegram_id = $2",
                encrypted_wallets, self.telegram_id
            )
            return True
        else:
            return False
            # print(f"Wallet already exists: {wallet}") # Debug

    async def remove_wallet(self, wallet, db_manager):
        decrypted_wallets = await self.get_wallets(db_manager)

        if wallet in decrypted_wallets:
            decrypted_wallets.remove(wallet)
            fernet = Fernet(settings.ENCRYPTION_KEY)
            encrypted_wallets = fernet.encrypt(json.dumps(decrypted_wallets).encode()).decode()

            await db_manager.execute_query(
                "UPDATE users SET encrypted_wallets = $1 WHERE telegram_id = $2",
                encrypted_wallets, self.telegram_id
            )
            return True
        else:
            return False
            # print(f"Wallet not found: {wallet}") # Debug

    async def get_wallets(self, db_manager):
        result = await db_manager.fetch_query(
            "SELECT encrypted_wallets FROM users WHERE telegram_id = $1", self.telegram_id
        )

        if not result or result[0]['encrypted_wallets'] is None:
            return []

        encrypted_wallets = result[0]['encrypted_wallets']
        fernet = Fernet(settings.ENCRYPTION_KEY)
        decrypted_wallets = json.loads(fernet.decrypt(encrypted_wallets.encode()).decode())

        return decrypted_wallets

    async def get_wallets(self, db_manager):
        result = await db_manager.fetch_query(
            "SELECT encrypted_wallets FROM users WHERE telegram_id = $1", self.telegram_id
        )

        if not result or result[0]['encrypted_wallets'] is None:
            return []

        encrypted_wallets_json = result[0]['encrypted_wallets']
        encrypted_wallets = json.loads(encrypted_wallets_json)
        fernet = Fernet(settings.ENCRYPTION_KEY)
        decrypted_wallets = [json.loads(fernet.decrypt(wallet.encode()).decode()) for wallet in encrypted_wallets]

        return decrypted_wallets

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
    async def get_user_by_telegram_id(cls, telegram_id: int, db_manager) -> "User":
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

            user = cls(**user_data)
            return user
        return None
