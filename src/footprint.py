# src\footprint.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dune_client.types import QueryParameter
from dune_client.client import DuneClient
from dune_client.query import Query
from config import settings

SUPPORTED_CHAINS = [
    {
        "name": "Layer Zero",
        "data_source": "Dune Analytics",
    }
]

class Footprint:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2) # Create a thread pool executor to run blocking code
        # Transpose API
        self.transpose_header = {
            'Content-Type': 'application/json',
            'X-API-KEY': settings.TRANSPOSE_API_KEY,
        }
        # Dune Analytics API
        self.dune = DuneClient(settings.DUNE_API_KEY)

    async def get_supported_chains(self):
        # Return chains name in a sorted list
        return sorted(SUPPORTED_CHAINS, key=lambda x: x['name'])

    async def get_dune_statistics(self, wallet_address, chain_name):
        if chain_name.lower() == "Layer Zero".lower():
            query_id = 2504714
        else:
            return None
        query = Query(
            name="Wallet Statistics",
            query_id=query_id,
            params=[
                QueryParameter.text_type(name="wallet_address", value=wallet_address),
            ],
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, self.dune.refresh, query)
            self.executor.shutdown()
            print(result.result.rows)
            return result.result.rows[0]
        except Exception as e:
            print(e)
            return None

    async def get_statistics(self, wallet_address, chain_name):
        # Get the statistics from the supported chains using the appropriate daa source
        data_source = [chain['data_source'] for chain in SUPPORTED_CHAINS if chain['name'].lower() == chain_name.lower()][0]
        if data_source == "Dune Analytics":
            return await self.get_dune_statistics(wallet_address, chain_name)


