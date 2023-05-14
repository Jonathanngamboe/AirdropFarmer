from config import settings
import hmac
import hashlib
from quart import request
import logging
import json


class IPNHandler:
    def __init__(self, db_manager, sys_logger):
        self.db_manager = db_manager
        self.cp_merchant_id = settings.COINPAYMENTS_MERCHANT_ID
        self.cp_ipn_secret = settings.COINPAYMENTS_IPN_SECRET
        self.cp_debug_email = settings.ADMIN_EMAIL
        self.sys_logger = sys_logger

    async def handle_ipn(self, ipn_data, telegram_bot):
        self.sys_logger.add_log(f"IPN received: {ipn_data}", logging.INFO)
        # Verify IPN mode
        ipn_mode = ipn_data.get("ipn_mode")
        if ipn_mode != "hmac":
            self.sys_logger.add_log("IPN Error: IPN Mode is not HMAC", logging.ERROR)

        # Verify HMAC signature
        hmac_signature = request.headers.get("HMAC")  # Change "HTTP_HMAC" to "HMAC"
        if not hmac_signature:
            self.sys_logger.add_log("IPN Error: No HMAC signature sent.", logging.ERROR)
            return "IPN Error: No HMAC signature sent."

        request_data = await request.get_data()
        generated_hmac = hmac.new(self.cp_ipn_secret.encode(), request_data, hashlib.sha512).hexdigest()

        if not hmac.compare_digest(generated_hmac, hmac_signature):
            self.sys_logger.add_log("IPN Error: HMAC signature does not match.", logging.ERROR)
            return "IPN Error: HMAC signature does not match"

        # Load variables
        merchant_id = ipn_data.get("merchant")
        if merchant_id != self.cp_merchant_id:
            self.sys_logger.add_log("IPN Error: No or incorrect Merchant ID passed", logging.ERROR)
            return "IPN Error: No or incorrect Merchant ID passed"

        transaction_id = ipn_data.get('txn_id')
        user_id = await self.db_manager.get_user_id_from_txn_id(transaction_id)
        if user_id is None:
            self.sys_logger.add_log(f"IPN Error: No user found for transaction {transaction_id}", logging.ERROR)
            return "IPN Error: No user found for transaction"

        self.sys_logger.add_log(
            f'IPN received for transaction {transaction_id} with status {ipn_data.get("status")} for user {user_id}',
            logging.INFO)

        # Save the transaction details to the database
        transaction_saved = await self.save_transaction_details(user_id, transaction_id, ipn_data)
        if transaction_saved:
            await self.process_ipn_request(transaction_id, ipn_data, user_id, telegram_bot)

    async def process_ipn_request(self, transaction_id, ipn_data, user_id, telegram_bot):
        # Process the IPN request based on the status code
        status = int(ipn_data.get('status'))

        if status >= 100 or status == 2:  # Payment is complete or queued for nightly payout
            # Get the user's subscription plan and duration
            transaction_data = await self.db_manager.get_transaction_by_id(transaction_id)
            if transaction_data is None:  # Check if transaction_data is None
                self.sys_logger.add_log(f"No transaction data found for transaction ID {transaction_id}", logging.ERROR)
                return
            duration = transaction_data['duration']
            self.sys_logger.add_log(f"Updating user {user_id} subscription to {ipn_data.get('item_name')} for {duration} days",
                                    logging.INFO)
            # Update user's subscription in the database.
            await self.db_manager.update_user_subscription(user_id, ipn_data.get('item_name'), duration)
            await self.notify_payment_complete(user_id, transaction_id, telegram_bot)
        elif status == -1:  # Payment cancelled/Timed out
            await self.notify_payment_timeout(user_id, transaction_id, telegram_bot)
        elif status == -2: # Payment refunded
            await self.notify_payment_refunded(user_id, transaction_id, telegram_bot)
        elif status <= -3: # Payment error
            await self.notify_payment_error(user_id, transaction_id, telegram_bot)
        else: # Payment is pending
            pass
            # Not needed for now
            # await self.notify_pending_payment(user_id, transaction_id, telegram_bot)

    async def save_transaction_details(self, user_id, transaction_id, ipn_data):
        if user_id is None:
            self.sys_logger.add_log(f"User ID not found for transaction {transaction_id}", logging.ERROR)
            return False
        self.sys_logger.add_log(f"Saving transaction details for transaction {transaction_id} for user {user_id}",
                                logging.INFO)

        # Convert the ipn_data to a JSON string
        ipn_data_json = json.dumps(dict(ipn_data))

        # Retrieve the existing transaction, if it exists
        existing_transaction = await self.db_manager.get_transaction_by_id(transaction_id)
        self.sys_logger.add_log(f"Existing transaction: {existing_transaction}", logging.INFO)

        # If the transaction exists, update only the specific columns
        if existing_transaction:
            # Here, we are using the duration from the existing transaction if it's available
            # If it's not (i.e., if it's None), we use settings.DAYS_IN_MONTH as a default value
            transaction_duration = existing_transaction['duration'] if existing_transaction['duration'] is not None else settings.DAYS_IN_MONTH
            await self.db_manager.save_transaction_details(user_id, transaction_id, ipn_data_json, transaction_duration)
            # If it doesn't exist, we don't do anything, this should never happen
        else:
            self.sys_logger.add_log(f"Transaction {transaction_id} not found in the database", logging.ERROR)

        return True

    async def notify_payment_timeout(self, user_id, transaction_id, telegram_bot):
        # Notify the user of the payment timeout
        message = f"Your payment has timed out without us receiving the required funds. If you need help, please type /contact to contact the support team and send your transaction ID: {transaction_id}"
        await self.send_payment_notification(user_id, message, telegram_bot)

    async def notify_payment_error(self, user_id, transaction_id, telegram_bot):
        self.sys_logger.add_log(f"Payment error for transaction {transaction_id} for user {user_id}", logging.ERROR)
        # Notify the user of the payment error
        message = f"Your payment encountered an error. If you need help, please type /contact to contact the support team and send your transaction ID: {transaction_id}"
        await self.send_payment_notification(user_id, message, telegram_bot)

    async def notify_payment_refunded(self, user_id, transaction_id, telegram_bot):
        # Notify the user of the payment refund
        message = f"Your payment for transaction {transaction_id} has been refunded. This is usually due to sending the wrong amount. If you need help, please type /contact to contact the support team and send your transaction ID: {transaction_id}"
        await self.send_payment_notification(user_id, message, telegram_bot)

    async def notify_payment_complete(self, user_id, transaction_id, telegram_bot):
        # Notify the user of the payment completion
        message = f"Your payment for transaction {transaction_id} has been received! Your subscription has been activated. Type /subscription to view your subscription details."
        await self.send_payment_notification(user_id, message, telegram_bot)

    async def notify_pending_payment(self, user_id, transaction_id, telegram_bot):
        # Notify the user of the pending payment
        message = f"Your payment is pending. We'll notify you once the payment is complete. If you need help, please type /contact to contact the support team and send your transaction ID: {transaction_id}"
        await self.send_payment_notification(user_id, message, telegram_bot)

    async def send_payment_notification(self, user_id, message, telegram_bot):
        self.sys_logger.add_log(f"Sending payment notification to user {user_id}: {message}", logging.INFO)
        try:
            await telegram_bot.bot.send_message(
                chat_id=user_id,
                text=message,
            )
            self.sys_logger.add_log(f"Payment notification sent to user {user_id}: {message}", logging.INFO)
        except Exception as e:
            self.sys_logger.add_log(f"Error sending payment notification to user {user_id}: {e}", logging.ERROR)