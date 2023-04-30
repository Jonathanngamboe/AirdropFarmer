# AirdropFarmer

AirdropFarmer is a Telegram bot that helps users manage and participate in airdrop events. It provides notifications for upcoming events, tracks user participation, and ensures the security of user data using encryption.

## Features

- Notifications for upcoming airdrop events
- Secure user data management with encryption
- User participation tracking
- Easy-to-use Telegram interface

## Prerequisites

- Python 3.6 or higher
- PostgreSQL 9.5 or higher
- A Telegram bot token
- An encryption key for securing user data
- A server with SSH access and systemd (for deployment)

## Installation and Setup

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/AirdropFarmer.git
   cd AirdropFarmer
   ```

2. Create a Python virtual environment and activate it:

   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required Python packages:

   ```
   pip install -r requirements.txt
   ```

4. Install PostgreSQL on your server:

   ```
   sudo apt-get update
   sudo apt-get install postgresql postgresql-contrib
   ```

5. Set up the PostgreSQL database and user:

   Replace `your_user`, `your_new_password`, and `your_database` with the desired values.

   ```
   sudo su - postgres
   psql
   CREATE DATABASE your_database;
   CREATE USER your_user WITH PASSWORD 'your_new_password';
   GRANT ALL PRIVILEGES ON DATABASE your_database TO your_user;
   \q
   exit
   ```

6. Set up environment variables:

   Copy the `.env.example` file to a new file called `.env`:
   ```
   cp .env.example .env
   ```

   Open the `.env` file and replace the placeholders with the appropriate values for `TELEGRAM_TOKEN`, `ENCRYPTION_KEY`, and `AIRDROP_FARMER_DATABASE_URL`. Save the file.

   Example:
   ```
   TELEGRAM_TOKEN=your_telegram_token
   ENCRYPTION_KEY=your_encryption_key
   AIRDROP_FARMER_DATABASE_URL=your_database_url
   ```

7. Configure the systemd service on your server:

   Create a new service file on your server:

   ```
   sudo nano /etc/systemd/system/airdropfarmer.service
   ```

   Add the following content to the file, replacing `<your_server_user>`, `<your_server_group>`, and `/path/to/AirdropFarmer` with the appropriate values:

   ```
   [Unit]
   Description=AirdropFarmer Telegram Bot
   After=network.target

   [Service]
   User=<your_server_user>
   Group=<your_server_group>
   WorkingDirectory=/path/to/AirdropFarmer
   ExecStart=/path/to/AirdropFarmer/venv/bin/python /path/to/AirdropFarmer/main.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Save and exit the editor.

   Enable and start the service:

   ```
   sudo systemctl enable airdropfarmer.service
   sudo systemctl start airdropfarmer.service
   ```

8. Configure GitHub Actions for deployment:

   Update the `deploy.yml` file in your repository as shown in the previous answer.

   Add the necessary secrets to your GitHub repository by going to "Settings" > "Secrets" and creating the following secrets:

   - `SERVER_SSH_PRIVATE_KEY`
   - `SERVER_USER`
   - `SERVER_IP`
   - `PORT`
   - `TELEGRAM_TOKEN`
   - `ENCRYPTION_KEY`
   - `AIRDROP_FARMER_DATABASE_URL`

   These secrets will be used by the GitHub Actions workflow to securely deploy your application to the server.

9. Push your changes to the repository:

   Whenever you push changes to the `master` branch, the GitHub Actions workflow will automatically deploy the updated code to your server.

   ```
   git add .
   git commit -m "Updated deployment configuration"
   git push origin master
   ```

10. Monitor the bot:

   To check the status of the AirdropFarmer service on your server, you can use the following command:

   ```
   sudo systemctl status airdropfarmer.service
   ```

   To view the logs for the AirdropFarmer service, use:

   ```
   sudo journalctl -u airdropfarmer.service -f
   ```

## Usage

1. Search for your bot on Telegram using its username.
2. Start a conversation with the bot and follow the prompts to manage and participate in airdrop events.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.