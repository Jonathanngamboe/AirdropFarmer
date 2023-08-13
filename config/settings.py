# settings.py

from decouple import config
from aiogram import types

# Telegram
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
ADMIN_TG_IDS = [1892238442]
ADMIN_COMMANDS = [
    types.BotCommand(command="send_update", description="Send an update to all users"),
    types.BotCommand(command="send_message", description="Send a message to a user"),
]
SUPPORT_TG_IDS = [1892238442]
SUPPORT_COMMANDS = [
    types.BotCommand(command="send_message", description="Send a message to a user"),
]
MAX_WALLET_NAME_LENGTH = 20

## Web3
BLOCKCHAIN_SETTINGS = {
    'ethereum': {
        'endpoint': 'https://eth.llamarpc.com',
        'explorer_url': 'https://etherscan.io/tx/',
        'weth_address': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
        'weth_abi': 'weth_mainnet_abi.json',
        'token_abi': 'erc20_abi.json'
    },
    'goerli': {
        'endpoint': 'https://eth-goerli.public.blastapi.io',
        'explorer_url': 'https://goerli.etherscan.io/tx/',
        'weth_address': '0xB4FBF271143F4FBf7B91A5ded31805e42b2208d6',
        'weth_abi': 'weth_mainnet_abi.json',
        'token_abi': 'erc20_abi.json'
    },
    'base_goerli': {
        'endpoint': 'https://base-goerli.public.blastapi.io',
        'explorer_url': 'https://goerli.etherscan.io/tx/',
        'weth_address': '0x4200000000000000000000000000000000000006',
        'weth_abi': 'weth_base_abi.json',
        'token_abi': 'erc20_abi.json'
    },
    'arbitrum_one': {
        'endpoint': 'https://endpoints.omniatech.io/v1/arbitrum/one/public',
        'explorer_url': 'https://arbiscan.io/tx/',
        'weth_address': '0x82af49447d8a07e3bd95bd0d56f35241523fbab1',
        'weth_abi': 'weth_mainnet_abi.json',
        'token_abi': 'erc20_abi.json'
    },
    'zkSync Era Mainnet': {
        'endpoint': 'https://mainnet.era.zksync.io',
        'explorer_url': 'https://explorer.zksync.io/tx/',
        'weth_address': '0x5aea5775959fbc2557cc8789bc1bf90a239d9a91',
        'weth_abi': 'weth_mainnet_abi.json',
        'token_abi': 'erc20_abi.json'
    },
    'zkSync Era Testnet': {
        'endpoint': 'https://testnet.era.zksync.dev',
        'explorer_url': 'https://zksync2-testnet.zkscan.io/tx/',
        'weth_address': '0x20b28b1e4665fff290650586ad76e977eab90c5d',
        'weth_abi': 'weth_mainnet_abi.json',
        'token_abi': 'erc20_abi.json'
    }
    # Add more blockchains here
}

DEFAULT_TRANSACTION_TIMEOUT = 120
GAS_PRICE_INCREASE = 1.2
MIN_WAITING_SEC = 30
MAX_WAITING_SEC = 300

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

### Footprint ###

# Covalent
COVALENT_API_KEY = config("COVALENT_API_KEY")

# Transpose
TRANSPOSE_API_KEY = config("TRANSPOSE_API_KEY")

# Dune Analytics
DUNE_API_KEY = config("DUNE_API_KEY")

### Footprint ###

# App
DAYS_IN_MONTH = 30
DAYS_IN_YEAR = 365
LOG_PATH = 'logs'
LOG_MAX_AGE_DAYS = 30
AIRDROP_FARMER_DATABASE_URL = config("AIRDROP_FARMER_DATABASE_URL")
# It's important to keep the order of the plans
SUBSCRIPTION_PLANS = [
    {
        'level': 'explorer_url (Free Plan)',
        'features': ['Access to basic airdrops', 'Single wallet'],
        'price_monthly': 0,
        'price_yearly': 0,
        'wallets': 1,
        'airdrop_limit': 1,
    },
    {
        'level': 'Adventurer (Basic Plan)',
        'features': ['New Airdrop alerts', 'Access to premium airdrops', 'Multiple wallets (up to 5 wallets)', 'Access to detailed log files', 'Priority support'],
        'price_monthly': 19.99,
        'price_yearly': 199.99,
        'wallets': 5,
        'airdrop_limit': 10,
    },
    {
        'level': 'Conqueror (Pro Plan)',
        'features': ['New Airdrop alerts', 'Priority access to new airdrops', 'Multiple wallets (up to 100 wallets)', 'Access to detailed log files', 'Priority support', 'Wallet generation (soon)', 'Discord and Twitter automation (soon)'],
        'price_monthly': 29.99,
        'price_yearly': 299.99,
        'wallets': 100,
        'airdrop_limit': 200,
        'most_popular': True,
    },
    {
        'level': 'Elite (Enterprise Plan)',
        'features': ['New Airdrop alerts', 'Exclusive airdrops and promotions', 'Unlimited wallets', 'Access to detailed log files', 'Priority access to new features' , 'Dedicated support', 'Wallet generation (soon)', 'Discord and Twitter automation (soon)'],
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

# Referral
MAX_REFERRAL_CODE_USES = 3
MAX_REFERRAL_CODE_GENERATION_PER_DAY = 1
REWARD_PERCENTAGE = 10