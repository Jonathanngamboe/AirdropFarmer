# db:manger.py

import os
import asyncpg
from config import settings


class DBManager:
    def __init__(self):
        self.db_connection = None

    async def init_db(self):
        self.db_connection = await asyncpg.connect(os.environ.get("AIRDROP_FARMER_DATABASE_URL"), timeout=settings.DB_TIMEOUT)

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
