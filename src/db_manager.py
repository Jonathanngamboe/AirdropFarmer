# db:manger.py

import os
import asyncpg
from config import settings


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
                username VARCHAR(255) NOT NULL,
                telegram_id BIGINT UNIQUE NOT NULL,
                subscription_level VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                airdrops TEXT[],
                encrypted_wallets JSONB,
                twitter_credentials JSONB,
                discord_credentials JSONB,
                session_logs JSONB
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
