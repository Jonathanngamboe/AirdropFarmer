# AirdropFarmer

AirdropFarmer is a Telegram bot that helps users manage and participate in airdrop events. It provides notifications for upcoming events, tracks user participation, and ensures the security of user data using encryption.

## Features

- Notifications for upcoming airdrop events
- Secure user data management with encryption
- User participation tracking
- Easy-to-use Telegram interface
- CoinPayments integration for transactions

## Prerequisites

- Python 3.7 or newer
- PostgreSQL 9.5 or higher
- A Telegram bot token
- An encryption key for securing user data
- A CoinPayments API key, API secret, merchant ID, and IPN secret
- An admin email address
- A server with SSH access and systemd (for deployment)
- GitHub Actions (for automated deployment)

## Installation and Setup

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/AirdropFarmer.git
   cd AirdropFarmer
   ```

2. Create a Python virtual environment and activate it:

   ```
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. Install the required Python packages:

   ```
   pip install -r requirements.txt
   ```

4. Generate an encryption key:

   Run the `generate_key.py` script in the `src` folder:

   ```
   python src/generate_key.py
   ```

   The script will output a generated encryption key. Make a note of this key, as you will need it for configuring the environment variables in the next step.

5. Set up the PostgreSQL database and user:

   Follow the instructions for your operating system to install and configure PostgreSQL. Create a new database and user, and grant the user all privileges on the database.

6. Set up environment variables:

   Copy the `.env.example` file to a new file called `.env`:
   ```
   cp .env.example .env
   ```

   Open the `.env` file and replace the placeholders with the appropriate values for `TELEGRAM_TOKEN`, `ENCRYPTION_KEY`, `AIRDROP_FARMER_DATABASE_URL`, `COINPAYMENTS_API_KEY`, `COINPAYMENTS_API_SECRET`, `ADMIN_EMAIL`, `COINPAYMENTS_MERCHANT_ID`, and `COINPAYMENTS_IPN_SECRET`. Use the encryption key generated in step 4. Save the file.

   Example:
   ```
   TELEGRAM_TOKEN=your_telegram_token
   ENCRYPTION_KEY=your_encryption_key
   AIRDROP_FARMER_DATABASE_URL=your_database_url
   COINPAYMENTS_API_KEY=your_coinpayments_api_public_key
   COINPAYMENTS_API_SECRET=your_coinpayments_api_private_key
   ADMIN_EMAIL=your_admin_email
   COINPAYMENTS_MERCHANT_ID=your_coinpayments_merchant_id
   COINPAYMENTS_IPN_SECRET=your_coinpayments_ipn_secret
   ```

7. Run the application:

   ```
   python main.py
   ```

   This command will start the AirdropFarmer Telegram bot and the Quart app to listen for IPN requests at http://localhost:5000/ipn.

8. Configure the systemd service on your server (optional):

   If you are deploying your application to a server and want to use systemd to manage the service, follow the instructions in the previous version of the README.md file.

9. Configure GitHub Actions for deployment (optional):

   If you want to use GitHub Actions for automated deployment, follow the instructions in the previous version of the README.md file.

## Usage

Interact with the AirdropFarmer Telegram bot using the Telegram app. You can use the bot to manage and participate in airdrop events, receive notifications, and track user participation.

To receive IPN notifications from CoinPayments, make sure your application is running and accessible at the IPN URL (http://localhost:5000/ipn by default). Configure your CoinPayments account to send IPN notifications to this URL.

## Troubleshooting

If you encounter any issues while setting up or running the AirdropFarmer Telegram bot, please follow these steps:

1. Check the logs for any error messages or warnings. You can find the logs in the same directory as your main.py file.

2. Make sure that your environment variables are correctly set in the `.env` file.

3. Ensure that your PostgreSQL database is running and properly configured.

4. Verify that your CoinPayments account is correctly set up with the correct API keys, merchant ID, and IPN secret.

5. Make sure your application is running and accessible at the IPN URL.

If you still encounter issues, feel free to ask for help or submit an issue on the GitHub repository.

## Contributing

If you would like to contribute to the AirdropFarmer project, please feel free to fork the repository, make your changes, and submit a pull request. We appreciate any contributions and improvements to the project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.