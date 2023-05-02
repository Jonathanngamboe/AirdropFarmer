# db:manger.py
import datetime
import asyncpg
from config import settings
from datetime import datetime, timedelta


class DBManager:
    def __init__(self):
        self.db_connection = None

    async def init_db(self):
        self.db_connection = await asyncpg.connect(settings.AIRDROP_FARMER_DATABASE_URL, timeout=settings.DB_TIMEOUT)
        await self.create_tables()

    async def create_tables(self):
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255),
                telegram_id BIGINT UNIQUE NOT NULL,
                subscription_level VARCHAR(255) NOT NULL,
                subscription_expiry TIMESTAMPTZ,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                airdrops TEXT[],
                encrypted_wallets JSONB,
                twitter_credentials JSONB,
                discord_credentials JSONB,
                session_logs JSONB
            );
        ''')
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users (id),
                transaction_id VARCHAR(255) UNIQUE NOT NULL,
                ipn_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')

    async def get_all_users(self):
        return await self.fetch_query("SELECT * FROM users;")

    async def close_db(self):
        if self.db_connection:
            await self.db_connection.close()

    async def execute_query(self, query, *args, **kwargs):
        try:
            result = await self.db_connection.execute(query, *args, **kwargs)
            return result
        except asyncpg.exceptions.InterfaceError:
            # Reconnect and retry if a connection error occurs
            await self.init_db()
            result = await self.db_connection.execute(query, *args, **kwargs)
            return result
        except Exception as e:
            # Handle other exceptions as appropriate
            raise e

    async def fetch_query(self, query, *args, **kwargs):
        try:
            result = await self.db_connection.fetchrow(query, *args, **kwargs)
            return result
        except asyncpg.exceptions.InterfaceError:
            # Reconnect and retry if a connection error occurs
            await self.init_db()
            result = await self.db_connection.fetchrow(query, *args, **kwargs)
            return result
        except Exception as e:
            # Handle other exceptions as appropriate
            raise e

    async def fetchval_query(self, query, *args, **kwargs):
        try:
            result = await self.db_connection.fetchval(query, *args, **kwargs)
            return result
        except asyncpg.exceptions.InterfaceError:
            # Reconnect and retry if a connection error occurs
            await self.init_db()
            result = await self.db_connection.fetchval(query, *args, **kwargs)
            return result
        except Exception as e:
            # Handle other exceptions as appropriate
            raise e

    async def save_transaction_details(self, user_id, transaction_id, ipn_data):
        # Save transaction details in your database
        await self.execute_query('''
            INSERT INTO transactions (user_id, transaction_id, ipn_data)
            VALUES ($1, $2, $3)
        ''', user_id, transaction_id, ipn_data)

    async def update_user_subscription(self, user_id, plan_name, duration):
        # Update the user's subscription in your database
        subscription_expiry = datetime.now() + timedelta(days=duration)
        await self.execute_query('''
            UPDATE users
            SET subscription_level=$1, subscription_expiry=$2
            WHERE id=$3
        ''', plan_name, subscription_expiry, user_id)

    async def get_user_id_from_txn_id(self, txn_id):
        return await self.fetchval_query('''
            SELECT user_id FROM transactions
            WHERE transaction_id=$1
        ''', txn_id)

    async def get_user_telegram_id(self, user_id):
        return await self.fetchval_query('''
            SELECT telegram_id FROM users
            WHERE id=$1
        ''', user_id)
