# user.py
import os
from datetime import datetime


class User:
    def __init__(self, user_id, telegram_id, username, subscription_level, db_manager):
        self.user_id = user_id
        self.telegram_id = telegram_id
        self.username = username
        self.subscription_level = subscription_level
        self.db_manager = db_manager
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
    async def create_user(cls, telegram_id, username, db_manager, subscription_level='free'):
        query = "INSERT INTO users (telegram_id, username, subscription_level, created_at) VALUES ($1, $2, $3, $4) RETURNING id"
        values = (telegram_id, username, subscription_level, datetime.utcnow())

        user_id = await db_manager.fetchval(query, *values)

        return cls(user_id, telegram_id, username, subscription_level, db_manager)

    @classmethod
    async def get_user_by_telegram_id(cls, telegram_id, db_manager):
        query = "SELECT id, telegram_id, username, subscription_level FROM users WHERE telegram_id = $1"
        values = (telegram_id,)

        user_data = await db_manager.fetch_query(query, *values)

        if user_data:
            return cls(*user_data, db_manager)
        else:
            return None