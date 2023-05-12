# secrets_manager.py
import logging
from typing import Optional
import hvac


class SecretsManager:
    def __init__(self, url: str, token: str, logger):
        self.client = hvac.Client(url=url, token=token)
        self.logger = logger

    def store_wallet(self, user_id: str, wallet: dict):
        try:
            existing_wallets = self.get_wallet(user_id) or []
            existing_wallets.append(wallet)
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f'users/{user_id}/wallets',
                secret={'wallets': existing_wallets},
                mount_point='secret',
            )
        except Exception as e:
            self.logger.add_log(f"Error during wallet storage: {e}", logging.ERROR)

    def delete_wallet(self, user_id: str, wallet: dict):
        existing_wallets = self.get_wallet(user_id)
        if wallet in existing_wallets:
            existing_wallets.remove(wallet)
            if existing_wallets:
                # If there are other wallets, overwrite with the updated list
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=user_id,
                    secret={'wallets': existing_wallets},
                    mount_point='secret',
                )
            else:
                # If there are no other wallets, delete all versions of the secret
                secret_metadata = self.client.secrets.kv.v2.read_secret_metadata(
                    path=user_id,
                    mount_point='secret',
                )
                versions = list(secret_metadata['data']['versions'].keys())
                self.client.secrets.kv.v2.delete_secret_versions(
                    path=user_id,
                    versions=versions,
                    mount_point='secret',
                )

    def get_wallet(self, user_id: str) -> Optional[list]:
        try:
            read_response = self.client.secrets.kv.v2.read_secret_version(
                path=user_id,
                mount_point='secret',
            )
            if read_response and 'data' in read_response and read_response['data']['metadata']['deletion_time'] == "":
                return read_response['data']['data'].get('wallets', [])
            else:
                return None
        except Exception as e:
            self.logger.add_log(f"Error during wallet retrieval: {e}", logging.ERROR)
            return None

