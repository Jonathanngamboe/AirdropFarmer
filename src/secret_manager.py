# secrets_manager.py
import logging
from typing import Optional
import hvac


class SecretsManager:
    def __init__(self, url: str, token: str, logger):
        self.client = hvac.Client(url=url, token=token)
        self.logger = logger

    def store_wallet(self, user_id: str, wallet: dict):
        existing_wallets = self.get_wallet(user_id)
        if existing_wallets is not None:
            existing_wallets.append(wallet)
        else:
            existing_wallets = [wallet]
        self.client.write(f'secret/data/{user_id}', data={'wallets': existing_wallets})

    def delete_wallet(self, user_id: str, wallet: dict):
        existing_wallets = self.get_wallet(user_id)
        if wallet in existing_wallets:
            existing_wallets.remove(wallet)
            if existing_wallets:
                # If there are other wallets, overwrite with the updated list
                self.client.write(f'secret/data/{user_id}', data={'wallets': existing_wallets})
            else:
                # If there are no other wallets, delete the entire secret
                self.client.delete(f'secret/data/{user_id}')

    def get_wallet(self, user_id: str) -> Optional[list]:
        try:
            read_response = self.client.read(f'secret/data/{user_id}')
            if read_response and 'data' in read_response:
                return read_response['data']['data'].get('wallets', [])
            else:
                return None
        except Exception as e:
            self.logger.add_log(f"Error during wallet retrieval: {e}", logging.ERROR)
            return None
