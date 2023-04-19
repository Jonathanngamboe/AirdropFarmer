# settings.py

# Discord
DISCORD_TOKEN = "NTM4MzMzODUyMTEzMDQzNDY2.GQhLNS.jQKTZAPT5BOZlxbgbUig1XvR8PovK90O4N06Wk"

# Telegram
TELEGRAM_TOKEN = "6150402247:AAEOityKxlnJGVjZe9wTZIEXoOZfGx-hBo0"
TELEGRAM_CHAT_ID = "1892238442"

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
INTERVAL = 60

# Waiting time between actions for each platform
PLATEFORM_WAIT_TIMES = {
    "twitter": 3000, # Seconds delay between Twitter actions
    "discord": 60, # Seconds delay between Discord actions
    "defi": 30 # Seconds delay between DeFi actions
}