# settings.py

from decouple import config

# Discord
DISCORD_TOKEN = "NTM4MzMzODUyMTEzMDQzNDY2.GQhLNS.jQKTZAPT5BOZlxbgbUig1XvR8PovK90O4N06Wk"

# Telegram
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
MAX_WALLET_NAME_LENGTH = 20

# Twitter
TWITTER_API_KEY = "votre_clé_api_twitter"
TWITTER_API_SECRET = "votre_clé_api_secrète_twitter"
TWITTER_ACCESS_TOKEN = "votre_token_d'accès_twitter"
TWITTER_ACCESS_TOKEN_SECRET = "votre_token_d'accès_secrète_twitter"

# Web3
# Ethereum Mainnet
ETHEREUM_MAINNET_ENDPOINT = "https://eth.llamarpc.com"
ETHEREUM_MAINNET_WETH_ADDRESS = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
# Ethereum Goerli
ETHEREUM_GOERLI_ENDPOINT = "https://eth-goerli.public.blastapi.io"
ETHEREUM_GOERLI_WETH_ADDRESS = "0xB4FBF271143F4FBf7B91A5ded31805e42b2208d6"
# Arbitrum One Mainnet
ARBITRUM_ONE_MAINNET_ENDPOINT = "https://endpoints.omniatech.io/v1/arbitrum/one/public"
# Base Chain Goerli
BASE_GOERLI_ENDPOINT = "https://base-goerli.public.blastapi.io"
BASE_GOERLI_WETH_ADDRESS = "0x4200000000000000000000000000000000000006"

DEFAULT_TRANSACTION_TIMEOUT = 120
GAS_PRICE_INCREASE = 1.2

# Wallets
WALLET_LIST = [
    {
        "address": "0x39a172848C9d94F7c73E92E563CD5cc7ca0B4A9F",
        "private_key": "c9f3504f667fd5a91d3d1bbe636e81da6c3439fc72fe4605bc9cab411c8d7a63"
    }
    # Ajoutez d'autres portefeuilles si nécessaire
]

# App
ENCRYPTION_KEY = config("ENCRYPTION_KEY")
AIRDROP_FARMER_DATABASE_URL = config("AIRDROP_FARMER_DATABASE_URL")
LOG_PATH = 'logs'
SUBSCRIPTION_LEVELS = [
            {
                'level': 'Basic',
                'features': ['Feature 1', 'Feature 2'],
                'price': '0',
                'wallets': '1',
            },
            {
                'level': 'Standard',
                'features': ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4'],
                'price': '0.1',
                'wallets': '100',
            },
            {
                'level': 'Premium',
                'features': ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4', 'Feature 5', 'Feature 6'],
                'price': '0.2',
                'wallets': '1000',
            },
            {
                'level': 'Custom',
                'features': ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4', 'Feature 5', 'Feature 6', 'Feature 7', 'Feature 8'],
                'price': '0.3',
                'wallets': 'Unlimited',
            },
        ]

# Waiting time between actions for each platform
PLATEFORM_WAIT_TIMES = {
    "twitter": 3000, # Seconds delay between Twitter actions
    "discord": 60, # Seconds delay between Discord actions
    "defi": 30 # Seconds delay between DeFi actions
}

# Database
MAX_DB_RETRIES = 5 # Number of times to retry a query if it fails
DB_TIMEOUT = 90 # Timeout for database queries