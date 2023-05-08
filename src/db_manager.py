# db:manger.py
import datetime
import asyncpg
from config import settings
from datetime import datetime, timedelta
from src.user import User


class DBManager:
    def __init__(self, logger):
        self.dsn = settings.AIRDROP_FARMER_DATABASE_URL
        self.timeout = settings.DB_TIMEOUT
        self.pool = None
        self.sys_logger = logger

    async def init_db(self):
        self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5, timeout=self.timeout)
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
                user_id INTEGER REFERENCES users (telegram_id) ON DELETE CASCADE,
                transaction_id VARCHAR(255) UNIQUE NOT NULL,
                ipn_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')

    async def get_all_users(self):
        return await self.fetch_query("SELECT * FROM users;")

    async def close_db(self):
        if self.pool:
            await self.pool.close()

    async def execute_query(self, query, *args, **kwargs):
        async with self.pool.acquire() as connection:
            try:
                result = await connection.execute(query, *args, **kwargs)
                return result
            except asyncpg.exceptions.UndefinedTableError:
                await self.init_db()
            except asyncpg.exceptions.InterfaceError:
                # Reconnect and retry if a connection error occurs
                result = await connection.execute(query, *args, **kwargs)
                return result
            except Exception as e:
                # Handle other exceptions as appropriate
                raise e

    async def fetch_query(self, query, *args, **kwargs):
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetch(query, *args, **kwargs)
                return result
            except asyncpg.exceptions.UndefinedTableError:
                await self.init_db()
            except asyncpg.exceptions.InterfaceError:
                # Reconnect and retry if a connection error occurs
                result = await connection.fetch(query, *args, **kwargs)
                return result
            except Exception as e:
                # Handle other exceptions as appropriate
                raise e

    async def fetchval_query(self, query, *args, **kwargs):
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetchval(query, *args, **kwargs)
                return result
            except asyncpg.exceptions.InterfaceError:
                # Reconnect and retry if a connection error occurs
                await self.init_db()
                result = await connection.fetchval(query, *args, **kwargs)
                return result
            except Exception as e:
                # Handle other exceptions as appropriate
                raise e

    async def save_transaction_details(self, user_id, transaction_id, ipn_data_json):
        self.sys_logger.add_log(f"Saving transaction {transaction_id} for user {user_id}")
        try:
            # Check if the user_id exists in the users table
            existing_user = await self.fetchval_query('''SELECT telegram_id FROM users WHERE telegram_id = $1''',
                                                      user_id)

            # If the user_id does not exist, create a new user
            if not existing_user:
                await User.create_user(user_id, None, self, self.sys_logger)

            # Check if the transaction_id already exists in the database
            existing_transaction = await self.fetchval_query(
                '''SELECT transaction_id FROM transactions WHERE transaction_id = $1''', transaction_id)

            # If the transaction_id exists, update the existing record
            if existing_transaction:
                self.sys_logger.add_log(
                    f"Transaction {existing_transaction} found in the database. Updating record.")
                await self.execute_query(
                    '''UPDATE transactions SET user_id = $1, ipn_data = $2 WHERE transaction_id = $3''', user_id,
                    ipn_data_json, transaction_id)
            # If the transaction_id does not exist, insert a new record
            else:
                await self.execute_query(
                    '''INSERT INTO transactions (user_id, transaction_id, ipn_data) VALUES ($1, $2, $3)''', user_id,
                    transaction_id, ipn_data_json)
                self.sys_logger.add_log(
                    f"Successfully saved transaction {transaction_id} for user {await self.get_user_id_from_txn_id(transaction_id)}")
            return True

        except Exception as e:
            self.sys_logger.add_log(f"Failed to save transaction details for transaction {transaction_id}: {e}")
            return False

    async def update_user_subscription(self, user_id, plan_name, duration):
        # Update the user's subscription in your database
        subscription_expiry = datetime.now() + timedelta(days=duration)
        await self.execute_query('''
            UPDATE users
            SET subscription_level=$1, subscription_expiry=$2
            WHERE telegram_id=$3
        ''', plan_name, subscription_expiry, user_id)

    async def get_user_id_from_txn_id(self, txn_id):
        user_id_record = await self.fetch_query('''
            SELECT user_id FROM transactions
            WHERE transaction_id=$1
        ''', txn_id)
        return user_id_record[0]['user_id'] if user_id_record else None

    async def get_user_telegram_id(self, user_id):
        return await self.fetchval_query('''
            SELECT telegram_id FROM users
            WHERE id=$1
        ''', user_id)

    async def get_user_subscription_expiry(self, user_id):
        return await self.fetchval_query('''
            SELECT subscription_expiry FROM users
            WHERE telegram_id=$1
        ''', user_id)

    async def get_transaction_by_id(self, transaction_id):
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetchrow('''
                    SELECT * FROM transactions WHERE transaction_id = $1
                ''', transaction_id)
                return result
            except asyncpg.exceptions.UndefinedTableError:
                await self.init_db()
            except asyncpg.exceptions.InterfaceError:
                # Reconnect and retry if a connection error occurs
                result = await connection.fetchrow('''
                    SELECT * FROM transactions WHERE transaction_id = $1
                ''', transaction_id)
                return result
            except Exception as e:
                # Handle other exceptions as appropriate
                raise e
