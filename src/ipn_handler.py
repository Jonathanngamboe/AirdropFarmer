from config import settings
import hmac
import hashlib
from quart import request
import logging


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
        hmac_signature = request.headers.get("HTTP_HMAC")
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

        status = int(ipn_data.get('status'))
        transaction_id = ipn_data.get('txn_id')

        user_id = await self.db_manager.get_user_id_from_txn_id(transaction_id)

        self.sys_logger.add_log(f'IPN received for transaction {transaction_id} with status {status} for user {user_id}', logging.INFO)

        if status >= 100 or status == 2:  # Payment is complete or queued for nightly payout
            await self.save_transaction_details(user_id, transaction_id, ipn_data)
            await self.update_user_subscription(user_id, ipn_data.get('item_name'),
                                                settings.SUBSCRIPTION_DURATION_DAYS)

            # Send payment received notification
            user_telegram_id = await self.db_manager.get_user_telegram_id(user_id)
            await self.on_payment_received(user_telegram_id, ipn_data, telegram_bot)
        elif status < 0:  # Payment error
            await self.notify_payment_error(user_id, transaction_id, ipn_data)
        else:  # Payment is pending
            await self.save_transaction_details(user_id, transaction_id, ipn_data)
            await self.notify_pending_payment(user_id, transaction_id, ipn_data)

    async def save_transaction_details(self, user_id, transaction_id, ipn_data):
        # Save transaction details to the database
        await self.db_manager.save_transaction_details(user_id, transaction_id, ipn_data)

    async def on_payment_received(self, user_telegram_id: int, payment_details: str, telegram_bot):
        try:
            await telegram_bot.send_message(
                chat_id=user_telegram_id,
                text=f"Your payment has been received! Details: {payment_details}",
            )
            print(f"Payment notification sent to user {user_telegram_id}")
            self.sys_logger.add_log(f"Payment notification sent to user {user_telegram_id}", logging.INFO)
        except Exception as e:
            self.sys_logger.add_log(f"Error sending payment notification to user {user_telegram_id}: {e}", logging.ERROR)

    async def update_user_plan(self, user_id, plan_name, duration):
        # Update user's plan in the database.
        await self.db_manager.update_user_subscription(user_id, plan_name, duration)

    async def notify_payment_timeout(self, user_id, transaction_id, ipn_data):
        # Notify the user of the payment timeout
        message = f"Your payment has timed out without us receiving the required funds. If you need help, please type /contact to contact our support team and send them your transaction ID: {transaction_id}"
        pass

    async def notify_payment_error(self, user_id, transaction_id, ipn_data):
        # Notify the user of the payment error
        pass

    async def notify_pending_payment(self, user_id, transaction_id, ipn_data):
        # Notify the user of the pending payment
        pass