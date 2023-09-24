# db:manger.py
import asyncpg
from config import settings
from datetime import datetime, timedelta, timezone
from src.user import User
import asyncio

class DBManager:
    def __init__(self, logger):
        """Initialize the database manager."""
        self.dsn = settings.AIRDROP_FARMER_DATABASE_URL
        self.timeout = settings.DB_TIMEOUT
        self.pool = None
        self.sys_logger = logger

    async def init_db(self):
        """Initialize the database connection and tables."""
        self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5, timeout=self.timeout)
        await self.create_tables()

    async def create_tables(self):
        """Create tables if they don't exist."""
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255),
                telegram_id BIGINT UNIQUE NOT NULL,
                subscription_level VARCHAR(255) NOT NULL,
                subscription_expiry TIMESTAMPTZ,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                airdrops JSONB,
                twitter_credentials JSONB,
                discord_credentials JSONB,
                session_logs JSONB,
                referral_code VARCHAR(255)
            );
        ''')
        await self.execute_query('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users (telegram_id) ON DELETE CASCADE,
                    transaction_id VARCHAR(255) UNIQUE NOT NULL,
                    ipn_data JSONB,
                    duration INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')
        await self.execute_query('''
                    CREATE TABLE IF NOT EXISTS referral_codes (
                        code_id SERIAL PRIMARY KEY,
                        code_value VARCHAR(255) UNIQUE NOT NULL,
                        created_by INTEGER REFERENCES users (telegram_id) ON DELETE CASCADE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        used_times INTEGER DEFAULT 0,
                        status BOOLEAN DEFAULT TRUE
                    );
                ''')
        await self.execute_query('''
                    CREATE TABLE IF NOT EXISTS rewards (
                        reward_id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users (telegram_id) ON DELETE CASCADE,
                        amount FLOAT NOT NULL,
                        claimed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS prepared_transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users (telegram_id) ON DELETE CASCADE,
                transaction_data JSONB,
                unique_key VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')

    async def get_all_users(self):
        return await self.fetch_query("SELECT * FROM users;")

    async def close_db(self):
        if self.pool:
            await self.pool.close()

    async def attempt_query(self, query_fn, query, *args, **kwargs):
        """Attempt to execute a query with retries."""
        retries = settings.MAX_DB_RETRIES
        delay = settings.DELAY_BETWEEN_DB_RETRIES  # in seconds

        for i in range(retries):
            async with self.pool.acquire() as connection:
                try:
                    result = await query_fn(connection, query, *args, **kwargs)
                    return result
                except asyncpg.exceptions.UndefinedTableError:
                    self.sys_logger.add_log("Table not found. Creating tables.")
                    await self.init_db()
                except (asyncpg.exceptions.InterfaceError, OSError):
                    if i < retries - 1:  # don't sleep on the last attempt
                        await asyncio.sleep(delay)
                        delay *= 2  # double the delay for exponential backoff
                    else:
                        raise  # if we've tried enough times, give up and raise the exception
                except Exception as e:
                    # Handle other exceptions as appropriate
                    self.sys_logger.add_log(f"An error occurred while executing query in the database: {e}")
                    raise e

    async def execute_query(self, query, *args, **kwargs):
        """Execute a single query."""
        return await self.attempt_query(lambda con, q, *a, **kw: con.execute(q, *a, **kw), query, *args, **kwargs)

    async def fetch_query(self, query, *args, **kwargs):
        return await self.attempt_query(lambda con, q, *a, **kw: con.fetch(q, *a, **kw), query, *args, **kwargs)

    async def fetchval_query(self, query, *args, **kwargs):
        return await self.attempt_query(lambda con, q, *a, **kw: con.fetchval(q, *a, **kw), query, *args, **kwargs)

    async def save_transaction_details(self, user_id, transaction_id, ipn_data_json, duration):
        """Save transaction details."""
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
                    '''UPDATE transactions SET user_id = $1, ipn_data = $2, duration = $3 WHERE transaction_id = $4''',
                    user_id,
                    ipn_data_json, duration, transaction_id)
            # If the transaction_id does not exist, insert a new record
            else:
                await self.execute_query(
                    '''INSERT INTO transactions (user_id, transaction_id, ipn_data, duration) VALUES ($1, $2, $3, $4)''',
                    user_id,
                    transaction_id, ipn_data_json, duration)
                self.sys_logger.add_log(
                    f"Successfully saved transaction {transaction_id} for user {await self.get_user_id_from_txn_id(transaction_id)}")
            return True

        except Exception as e:
            self.sys_logger.add_log(f"Failed to save transaction details for transaction {transaction_id}: {e}")
            return False

    async def update_user_subscription(self, user_id, plan_name, duration):
        """Update the user's subscription."""
        subscription_expiry = datetime.now(timezone.utc) + timedelta(days=duration)
        await self.execute_query('''
            UPDATE users
            SET subscription_level=$1, subscription_expiry=$2
            WHERE telegram_id=$3
        ''', plan_name, subscription_expiry, user_id)

    async def check_and_update_expired_subscriptions(self):
        # Get current date
        current_date = datetime.now(timezone.utc)

        try:
            # Query for all users whose subscriptions have expired and are not yet set to 'expired'
            expired_users = await self.fetch_query(
                "SELECT * FROM users WHERE subscription_expiry <= $1 AND subscription_level != $2;",
                current_date, settings.SUBSCRIPTION_PLANS[0]['level'])

            # Update user plans
            for user in expired_users:
                user_id = user['telegram_id']
                await self.execute_query(
                    "UPDATE users SET subscription_level = $1 WHERE telegram_id = $2;",
                    settings.SUBSCRIPTION_PLANS[0]['level'], user_id)
                self.sys_logger.add_log(f"Subscription for user {user_id} has been set to 'expired'")
        except Exception as e:
            self.sys_logger.add_log(f"Failed to update expired subscriptions: {e}")

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
        self.sys_logger.add_log(f"Getting transaction {transaction_id}")
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetchrow('''
                    SELECT * FROM transactions WHERE transaction_id = $1
                ''', transaction_id)
                return result
            except asyncpg.exceptions.UndefinedTableError:
                self.sys_logger.add_log("Transactions table not found. Creating table...")
                await self.init_db()
            except asyncpg.exceptions.InterfaceError:
                # Reconnect and retry if a connection error occurs
                self.sys_logger.add_log("Connection error. Reconnecting...")
                result = await connection.fetchrow('''
                    SELECT * FROM transactions WHERE transaction_id = $1
                ''', transaction_id)
                return result
            except Exception as e:
                self.sys_logger.add_log(f"Failed to get transaction {transaction_id}: {e}")
                raise e

    async def delete_user(self, telegram_id):
        """Delete a user and their related data."""
        # Get all referral_codes created by the user
        referral_codes = await self.fetch_query('''
            SELECT code_value FROM referral_codes
            WHERE created_by=$1
        ''', telegram_id)

        # Update referral_code to NULL for all users who used any of this user's referral_codes
        for row in referral_codes:
            referral_code = row['code_value']
            await self.execute_query('''
                UPDATE users
                SET referral_code = NULL
                WHERE referral_code = $1
            ''', referral_code)

        # Here we are using DELETE CASCADE to delete all related entries in transactions table
        await self.execute_query('''
            DELETE FROM users
            WHERE telegram_id=$1
        ''', telegram_id)
