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
            existing_wallets = self.get_wallet(user_id)
            if existing_wallets is None:
                # No existing wallets, create new secret
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f'users/{user_id}/wallets',
                    secret={'wallets': [wallet]},
                    mount_point='secret',
                )
            else:
                # Existing wallets found, append new wallet and update secret
                existing_wallets.append(wallet)
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f'users/{user_id}/wallets',
                    secret={'wallets': existing_wallets},
                    mount_point='secret',
                )
        except Exception as e:
            self.logger.add_log(f"Error during wallet storage: {e}", logging.ERROR)

    def delete_wallet(self, user_id: str, wallet: dict):
        try:
            existing_wallets = self.get_wallet(user_id) or []
            self.logger.add_log(f"Existing wallets: {existing_wallets}")
            if wallet in existing_wallets:
                existing_wallets.remove(wallet)
                if existing_wallets:
                    # If there are other wallets, overwrite with the updated list
                    self.client.secrets.kv.v2.create_or_update_secret(
                        path=f'users/{user_id}/wallets',
                        secret={'wallets': existing_wallets},
                        mount_point='secret',
                    )
                else:
                    # If there are no other wallets, delete all versions of the secret
                    secret_metadata = self.client.secrets.kv.v2.read_secret_metadata(
                        path=f'users/{user_id}/wallets',
                        mount_point='secret',
                    )
                    versions = list(secret_metadata['data']['versions'].keys())
                    self.client.secrets.kv.v2.delete_secret_versions(
                        path=f'users/{user_id}/wallets',
                        versions=versions,
                        mount_point='secret',
                    )
        except Exception as e:
            self.logger.add_log(f"Error during wallet deletion: {e}", logging.ERROR)

    def get_wallet(self, user_id: str) -> Optional[list]:
        try:
            # Check if data exists at the path
            self.client.secrets.kv.v2.read_secret_metadata(
                path=f'users/{user_id}/wallets',
                mount_point='secret',
            )
            # If no exception was raised, data exists. Proceed with retrieval.
            read_response = self.client.secrets.kv.v2.read_secret_version(
                path=f'users/{user_id}/wallets',
                mount_point='secret',
            )
            if read_response and 'data' in read_response and read_response['data']['metadata']['deletion_time'] == "":
                return read_response['data']['data'].get('wallets', [])
            else:
                return None
        except hvac.exceptions.InvalidPath:
            self.logger.add_log(f"No data found for user {user_id}", logging.WARNING)
            return None
        except Exception as e:
            self.logger.add_log(f"Error during wallet retrieval for user {user_id}: {e}", logging.ERROR)
            return None
