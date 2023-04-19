# user.py
import os
from datetime import datetime

import asyncpg


class User:
    def __init__(self, user_id, telegram_id, username, subscription_level):
        self.user_id = user_id
        self.telegram_id = telegram_id
        self.username = username
        self.subscription_level = subscription_level
    def add_wallet(self, wallet):
        self.wallet.append(wallet)

    def add_wallet(self, wallet):
        self.wallets.append(wallet)
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
        conn = await asyncpg.connect("postgres://username:password@localhost/dbname")
        await conn.execute(
            "UPDATE users SET subscription_level=$1 WHERE telegram_id=$2",
            subscription_level,
            self.telegram_id,
        )
        await conn.close()

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
    async def create_user(cls, telegram_id, username, subscription_level='free'):
        conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))

        query = "INSERT INTO users (telegram_id, username, subscription_level, created_at) VALUES ($1, $2, $3, $4) RETURNING id"
        values = (telegram_id, username, subscription_level, datetime.utcnow())

        user_id = await conn.fetchval(query, *values)

        await conn.close()

        return cls(user_id, telegram_id, username, subscription_level)

    @classmethod
    async def get_user_by_telegram_id(cls, telegram_id):
        conn = await asyncpg.connect("postgres://username:password@localhost/dbname")

        query = "SELECT id, telegram_id, username, subscription_level FROM users WHERE telegram_id = $1"
        values = (telegram_id,)

        user_data = await conn.fetchrow(query, *values)

        await conn.close()

        if user_data:
            return cls(*user_data)
        else:
            return None