# src\footprint.py
import asyncio

import aiohttp
import requests
from config import settings

class Footprint:
    def __init__(self):
        # Covalent API
        self.covalent_header = {"accept": "application/json"}
        self.covalent_basic = (settings.COVALENT_API_KEY, "")

    async def get_wallet_transactions(self, wallet_address, blockchain_name):
        url = f"https://api.covalenthq.com/v1/{blockchain_name}/address/{wallet_address}/transactions_v2/"
        try:
            response = requests.get(url, headers=self.covalent_header, auth=self.covalent_basic)
        except Exception as e:
            raise e
        transactions = response.json().get('data', {}).get('items', [])

        volume, fees, txn_count = 0, 0, 0
        # Get the volume, fees and txn count
        for txn in transactions:
            if txn['from_address'].lower() == wallet_address.lower():
                fees += int(txn['gas_quote'])
                if txn['successful']:
                    txn_count += 1
                    volume += int(txn['value_quote'])

        last_interaction_time = transactions[0]['block_signed_at'] if transactions else None
        last_interaction_time = last_interaction_time.replace('T', ' ').replace('Z', '') if last_interaction_time else None
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
                data = await response.json()
                response = data.get('data', {}).get('items', [])
                chains = []
                for chain in response:
                    # Save chain name and label
                    chains.append({'name': chain['name'], 'label': chain['label']})
                # Sort the chains by name
                sorted_chains = sorted(chains, key=lambda k: k['label'])
                return sorted_chains

    async def get_blockchain_name(self, blockchain_name_or_label):
        supported_chains = await self.get_supported_chains()
        for chain in supported_chains:
            if blockchain_name_or_label.lower() == chain['name'].lower() or blockchain_name_or_label.lower() == chain[
                'label'].lower():
                return chain['name']
        # If no match is found, return the original value.
        return blockchain_name_or_label

    async def get_statistics(self, wallet_address, blockchain_name_or_label):
        blockchain_name = await self.get_blockchain_name(blockchain_name_or_label)
        data = await self.get_wallet_transactions(wallet_address, blockchain_name)
        if not data:
            return None
        return data

