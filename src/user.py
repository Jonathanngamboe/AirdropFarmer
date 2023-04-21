# user.py
import os
from datetime import datetime


class User:
    def __init__(self, telegram_id, username, subscription_level, airdrops=None):
        self.telegram_id = telegram_id
        self.username = username
        self.subscription_level = subscription_level
        self.airdrops = airdrops if airdrops is not None else []

    async def update_airdrops(self, db_manager):
        airdrops_str = '{' + ','.join([f'"{name}"' for name in self.airdrops]) + '}'
        await db_manager.execute_query(
            "UPDATE users SET airdrops = $1 WHERE telegram_id = $2",
            list(self.airdrops), self.telegram_id
        )

    def add_wallet(self, wallet):
        if wallet not in self.wallet:
            self.wallet.append(wallet)
        # Update the user's wallets in the database

    def remove_wallet(self, wallet):
        if wallet in self.wallets:
            self.wallets.remove(wallet)
        # Update the user's wallets in the database

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

    def get_wallets(self):
        # Retrieve the user's wallets from the database
        return self.wallets

    def get_session_logs(self):
        # Retrieve the user's session logs from the database
        return self.session_logs

    def get_subscription_info(self):
        subscription_levels = {
            'free': {
                'level': 'Free',
                'features': ['Feature 1', 'Feature 2']
            },
            'premium': {
                'level': 'Premium',
                'features': ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4']
            }
        }

        return subscription_levels[self.subscription_level]

    @classmethod
    async def create_user(cls, telegram_id, username, db_manager):
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'subscription_level': 'free',
        }
        user = cls(**user_data)
        await db_manager.execute_query(  # Replace 'execute' with 'execute_query'
            "INSERT INTO users (telegram_id, username) VALUES ($1, $2)",
            telegram_id,
            username,
        )
        return user

    @classmethod
    async def get_user_by_telegram_id(cls, telegram_id: int, db_manager) -> "User":
        user_data = await db_manager.fetch_query(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )

        if user_data:
            user_data = dict(user_data)  # Convert the asyncpg.Record object to a dictionary
            user_data.pop('id', None)  # Remove 'id' from the user_data dictionary, this id is only used in the database
            user_data.pop('created_at',
                          None)  # Remove 'created_at' from the user_data dictionary, this is only used in the database
            user = cls(**user_data)
            if user.airdrops:
                user.airdrops = list(user.airdrops)  # Convert the text array to a Python list
            else:
                user.airdrops = []
            return user
        return None