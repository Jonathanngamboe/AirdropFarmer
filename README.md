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
- A Vault instance for storing application secrets
- A CoinPayments API key, API secret, merchant ID, and IPN secret
- An admin email address
- A server with SSH access and systemd (for deployment)
- Nginx web server (for reverse proxy)
- GitHub Actions (for automated deployment)

## Installation and Setup

1. Create a new user and add it to the necessary groups:

   ```
   sudo adduser airdropfarmer
   sudo usermod -aG sudo airdropfarmer
   ```

2. Switch to the new user:

   ```
   sudo su - airdropfarmer
   ```

3. Clone the repository:

   ```
   git clone https://github.com/yourusername/AirdropFarmer.git
   cd AirdropFarmer
   ```

4. Create a Python virtual environment and activate it:

   ```
   python -m venv venv
   source venv/bin/activate
   ```

5. Install the required Python packages:

   ```
   pip install -r requirements.txt
   ```

6. Set up Vault (optional but recommended):

   If you prefer not to store your sensitive information in the .env file, you can use HashiCorp's Vault. After setting up a Vault instance, you can store your secrets there.
   
   Note: The current deployment script assumes you are using Vault to store your secrets. If you choose not to use Vault, you'll need to modify the deployment script accordingly.

7. Set up the PostgreSQL database and user:

   Follow the instructions for your operating system to install and configure PostgreSQL. Create a new database and user, and grant the user all privileges on the database.

8. Set up environment variables:

   Copy the `.env.example` file to a new file called `.env`:
   ```
   cp .env.example .env
   ```

   Open the `.env` file and replace the placeholders with the appropriate values for `TELEGRAM_TOKEN`, `ENCRYPTION_KEY`, `AIRDROP_FARMER_DATABASE_URL`, `COINPAYMENTS_API_KEY`, `COINPAYMENTS_API_SECRET`, `ADMIN_EMAIL`, `COINPAYMENTS_MERCHANT_ID`, and `COINPAYMENTS_IPN_SECRET`. Use the encryption key generated in step 6. Save the file.

   Example:
   ```
   TELEGRAM_TOKEN=<your telegram bot token>
   AIRDROP_FARMER_DATABASE_URL=<your postgre database url>
   COINPAYMENTS_PUBLIC_KEY=<your coinpayments api private key>
   COINPAYMENTS_PRIVATE_KEY=<your coinpayments api public key>
   COINPAYMENTS_MERCHANT_ID=<your coinpayments merchant id>
   COINPAYMENTS_IPN_SECRET=<your coinpayments ipn secret>
   ADMIN_EMAIL=<your admin email>
   SERVER_IP=<your server ip>
   VAULT_TOKEN=<your vault token>
   VAULT_URL=<your vault address>
   ```

9. Run the application:

   ```
   python main.py
   ```

   This command will start the AirdropFarmer Telegram bot and the Quart app to listen for IPN requests at http://localhost:8000/ipn.


10. Configure the systemd service on your server (optional):

   If you are deploying your application to a server and want to use systemd to manage the service, follow these instructions:

   a. Create a systemd service file with the new user and paths:

      ```
      sudo nano ~/.config/systemd/user/airdropfarmer.service
      ```

      Create the content as follows:

      ```ini
      [Unit]
      Description=AirdropFarmer Telegram Bot
      After=network.target

      [Service]
      User=airdropfarmer
      WorkingDirectory=/home/airdropfarmer/AirdropFarmer/
      EnvironmentFile=/home/airdropfarmer/AirdropFarmer/.env
      ExecStart=/home/airdropfarmer/AirdropFarmer/venv/bin/python main.py
      Restart=always

      [Install]
      WantedBy=multi-user.target
      ```

      Save and exit the editor.

   b. Reload the systemd configuration and restart the AirdropFarmer service:

      ```
      sudo systemctl --user daemon-reload
      sudo systemctl --user restart airdropfarmer.service
      ```

   c. Check the status of the service and view the logs again to see if the issue is resolved:

      ```
      sudo systemctl --user status airdropfarmer.service
      sudo journalctl --user-unit=airdropfarmer.service -f
      ```

11. Configure Nginx as a reverse proxy:

   a. Install Nginx on your server.

   b. Create a new Nginx configuration file for AirdropFarmer:

      ```
      sudo nano /etc/nginx/sites-available/AirdropFarmer
      ```

   c. Add the following configuration to the file, replacing `airdropfarmer.com` and `www.airdropfarmer.com` with your domain name, and update the SSL certificate and key paths as necessary:

      ```
      server {
          listen 80;
          server_name airdropfarmer.com www.airdropfarmer.com;
          return 301 https://$host$request_uri;
      }

      server {
          listen 443 ssl http2;
          server_name airdropfarmer.com www.airdropfarmer.com;

          ssl_certificate /etc/letsencrypt/live/airdropfarmer.com/fullchain.pem;
          ssl_certificate_key /etc/letsencrypt/live/airdropfarmer.com/privkey.pem;
          ssl_protocols TLSv1.2 TLSv1.3;
          ssl_ciphers 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384';

          location / {
              proxy_pass http://127.0.0.1:8000;
              proxy_set_header Host $host;
              proxy_set_header X-Real-IP $remote_addr;
              proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
              proxy_set_header X-Forwarded-Proto $scheme;
          }
      }
      ```

   d. Create a symbolic link to the configuration file in the `sites-enabled` directory:

      ```
      sudo ln -sf /etc/nginx/sites-available/AirdropFarmer /etc/nginx/sites-enabled/
      ```

   e. Test the Nginx configuration and restart the service:

      ```
      sudo nginx -t
      sudo systemctl restart nginx
      ```

12. Configure GitHub Actions for deployment (optional):

   If you want to use GitHub Actions for automated deployment, follow the instructions in the previous version of the README.md file.

## Usage

Interact with the AirdropFarmer Telegram bot using the Telegram app. You can use the bot to manage and participate in airdrop events, receive notifications, and track user participation.

To receive IPN notifications from CoinPayments, make sure your application is running and accessible at the IPN URL (https://yourdomain.com/ipn by default). Configure your CoinPayments account to send IPN notifications to this URL.

Note: This application is configured to fetch secrets from a Vault instance. Please ensure that the Vault is running and accessible, and that the correct Vault token is provided.

## Troubleshooting

If you encounter any issues while setting up or running the AirdropFarmer Telegram bot, please follow these steps:

1. Check the logs for any error messages or warnings. You can find the logs in the same directory as your main.py file.

2. Make sure that your environment variables are correctly set in the `.env` file.

3. Ensure that your PostgreSQL database is running and properly configured.

4. Verify that your CoinPayments account is correctly set up with the correct API keys, merchant ID, and IPN secret.

5. Make sure your application is running and accessible at the IPN URL.

6. If you are using Nginx as a reverse proxy, check the Nginx configuration, logs, and ensure that the service is running.

7. If you are using Vault to store your secrets, make sure that your Vault instance is running and that the application has the necessary permissions to fetch the secrets.

If you still encounter issues, feel free to ask for help or submit an issue on the GitHub repository.

## Contributing

If you would like to contribute to the AirdropFarmer project, please feel free to fork the repository, make your changes, and submit a pull request. We appreciate any contributions and improvements to the project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.