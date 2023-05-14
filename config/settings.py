# settings.py

from decouple import config

# Telegram
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
ADMIN_TELEGRAM_ID = 1892238442
MAX_WALLET_NAME_LENGTH = 20

## Web3
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

# Coinpayments API
COINPAYMENTS_PUBLIC_KEY = config("COINPAYMENTS_PUBLIC_KEY")
COINPAYMENTS_PRIVATE_KEY = config("COINPAYMENTS_PRIVATE_KEY")
COINPAYMENTS_MERCHANT_ID = config("COINPAYMENTS_MERCHANT_ID")
COINPAYMENTS_IPN_SECRET = config("COINPAYMENTS_IPN_SECRET")
IPN_PORT = 5000
IPN_ROUTE = '/ipn'
SERVER_IP = config("SERVER_IP")
COINPAYMENTS_IPN_URL = f'http://{SERVER_IP}:{IPN_PORT}{IPN_ROUTE}'
ADMIN_EMAIL = config("ADMIN_EMAIL")

# Vault
VAULT_TOKEN = config("VAULT_TOKEN")
VAULT_URL = config("VAULT_URL")

# App
LOG_PATH = 'logs'
LOG_MAX_AGE_DAYS = 7
AIRDROP_FARMER_DATABASE_URL = config("AIRDROP_FARMER_DATABASE_URL")
SUBSCRIPTION_DURATION_DAYS = 30
# It's important to keep the order of the plans
SUBSCRIPTION_PLANS = [
    {
        'level': 'Explorer (Free Plan)',
        'features': ['Access to basic airdrops', 'Single wallet'],
        'price_monthly': 0,
        'price_yearly': 0,
        'wallets': 1,
        'airdrop_limit': 1,
    },
    {
        'level': 'Adventurer (Basic Plan)',
        'features': ['New Airdrop alerts', 'Access to premium airdrops', 'Multiple wallets (up to 5 wallets)', 'Access to detailed log files', 'Priority support'],
        'price_monthly': 9.99,
        'price_yearly': 99.99,
        'wallets': 5,
        'airdrop_limit': 10,
    },
    {
        'level': 'Conqueror (Pro Plan)',
        'features': ['New Airdrop alerts', 'Priority access to new airdrops', 'Multiple wallets (up to 100 wallets)', 'Access to detailed log files', 'Discord and Twitter automation', 'Priority support'],
        'price_monthly': 19.99,
        'price_yearly': 199.99,
        'wallets': 100,
        'airdrop_limit': 200,
        'most_popular': True,
    },
    {
        'level': 'Elite (Enterprise Plan)',
        'features': ['New Airdrop alerts', 'Exclusive airdrops and promotions', 'Unlimited wallets', 'Access to detailed log files', 'Discord and Twitter automation', 'Priority access to new features', 'Dedicated support'],
        'price_monthly': 'Custom',
        'price_yearly': 'Custom',
        'airdrop_limit': None,
        'wallets': '♾ (Unlimited)',
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