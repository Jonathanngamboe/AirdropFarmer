# src\footprint.py

import aiohttp
from config import settings

SUPPORTED_CHAINS = [
    {
        'name': 'arbitrum-goerli',
        'label': 'Arbitrum Goerli',
    },
    {
        'name': 'arbitrum-mainnet',
        'label': 'Arbitrum Mainnet',
    },
    {
        'name': 'arbitrum-nova-mainnet',
        'label': 'Arbitrum Nova Mainnet',
    },
    {
        'name': 'base-testnet',
        'label': 'Base Testnet',
    },
    {
        'name': 'linea-testnet',
        'label': 'Linea Testnet',
    },
    {
        'name': 'optimism-mainnet',
        'label': 'Optimism Mainnet',
    },
    {
        'name': 'optimism-goerli',
        'label': 'Optimism Goerli',
    },
    {
        'name': 'polygon-zkevm-mainnet',
        'label': 'Polygon ZK-EVM Mainnet',
    },
    {
        'name': 'polygon-zkevm-testnet',
        'label': 'Polygon ZK-EVM Testnet',
    },
    {
        'name': 'scroll-alpha-testnet',
        'label': 'Scroll Alpha Testnet',
    }
]


class Footprint:
    def __init__(self):
        # Covalent API
        self.covalent_header = {"accept": "application/json"}
        self.covalent_basic = (settings.COVALENT_API_KEY, "")

    async def get_wallet_transactions(self, wallet_address, blockchain_name):
        url = f"https://api.covalenthq.com/v1/{blockchain_name}/address/{wallet_address}/transactions_v2/"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.covalent_header,
                                   auth=aiohttp.BasicAuth(*self.covalent_basic)) as response:
                try:
                    data = await response.json()
                    print(data)
                    if data.get('error'):
                        raise ValueError(f"Error: {data.get('error_message')}")
                    transactions = data.get('data', {}).get('items', [])
                except Exception as e:
                    raise e

        volume, fees, txn_count = 0, 0, 0

        # fetch the supported chains
        supported_chains = await self.get_supported_chains()

        # find the appropriate blockchain
        blockchain = next((b for b in supported_chains if b['name'] == blockchain_name), None)
        if not blockchain:
            raise ValueError("Unsupported blockchain name.")

        # Get the volume, fees and txn count
        for txn in transactions:
            if txn['from_address'].lower() == wallet_address.lower():
                fees += int(txn['fees_paid']) * 10 ** -18 if txn['fees_paid'] else 0
                if txn['successful']:
                    txn_count += 1
                    volume += int(txn['value']) * 10 ** -18 if txn['value'] else 0

        if txn_count == 0:
            return None

        # Round the volume and fees
        volume = round(volume, 3)
        fees = round(fees, 6)

        # Add symbol to the volume and fees
        # TODO: Find a better way to get the symbol
        if blockchain_name == 'polygon-zkevm-testnet':
            volume = f"{volume} MATIC"
            fees = f"{fees} MATIC"
        else:
            volume = f"{volume} ETH"
            fees = f"{fees} ETH"

        # Get the last interaction time if it was successful and made by the wallet address
        last_interaction_time = transactions[0]['block_signed_at'] if transactions[0]['successful'] and transactions[0][
            'from_address'].lower() == wallet_address.lower() else None
        last_interaction_time = last_interaction_time.replace('T', ' ').replace('Z',
                                                                                '') if last_interaction_time else None
        data = {
            'interactions': txn_count,
            'volume': volume,
            'last_interaction_time': last_interaction_time,
            'fees': fees,
        }
        return data

    async def get_supported_chains(self):
        url='https://api.covalenthq.com/v1/chains/'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.covalent_header, auth=aiohttp.BasicAuth(*self.covalent_basic)) as response:
                try:
                    data = await response.json()
                    response = data.get('data', {}).get('items', [])
                    chains = []
                    for chain in response:
                        # Save chain name and label if the chain is supported in SUPPORTED_CHAINS
                        if chain['name'] in [supported_chain['name'] for supported_chain in SUPPORTED_CHAINS]:
                            chains.append({'name': chain['name'], 'label': chain['label']})

                    # Add the SUPPORTED_CHAINS to the list if they are not returned by Covalent
                    # TODO: Remove this section when all chains are returned by Covalent
                    for supported_chain in SUPPORTED_CHAINS:
                        if supported_chain['name'] not in [chain['name'] for chain in chains]:
                            chains.append(supported_chain)

                    # Sort the chains by name
                    sorted_chains = sorted(chains, key=lambda k: k['label'])
                    return sorted_chains
                except Exception as e:
                    raise e

    async def get_blockchain_name(self, blockchain_name_or_label):
        supported_chains = await self.get_supported_chains()
        for chain in supported_chains:
            if blockchain_name_or_label.lower() == chain['name'].lower() or blockchain_name_or_label.lower() == chain[
                'label'].lower():
                return chain['name']
        # If no match is found, return the original value.
        return blockchain_name_or_label

    # TODO: Complete this function
    async def get_rank(self, wallet_address, blockchain_name):
        try:
            data = {}

            data['percentage_less_active'] = (data['less_active_wallets'] / data['total_wallets']) * 100
            data['percentage_less_spending'] = (data['less_spending_wallets'] / data['total_wallets']) * 100

            # Round the percentages to 0 decimal places
            data['percentage_less_active'] = round(data['percentage_less_active'], 0)

            # Add a % sign to the percentages
            data['percentage_less_active'] = str(data['percentage_less_active']) + '%'
            data['percentage_less_spending'] = str(data['percentage_less_spending']) + '%'


            # Remove unnecessary keys
            data.pop('less_active_wallets')
            data.pop('less_spending_wallets')
            data.pop('total_wallets')

            return data
        except Exception as e:
            print(e)

    async def get_statistics(self, wallet_address, blockchain_name_or_label):
        blockchain_name = await self.get_blockchain_name(blockchain_name_or_label)
        data = await self.get_wallet_transactions(wallet_address, blockchain_name)
        #ranks = await self.get_rank(wallet_address, blockchain_name)
        # Add new keys to the data
        #data['percentage_less_spending'] = ranks['percentage_less_spending']
        #data['percentage_less_active'] = ranks['percentage_less_active']
        if not data:
            return None
        return data

