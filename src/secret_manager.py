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
                self.logger.add_log(f"Creating new secret for user {user_id}", logging.INFO)
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f'users/{user_id}/wallets',
                    secret={'wallets': [wallet]},
                    mount_point='secret',
                )
            else:
                # Existing wallets found, append new wallet and update secret
                self.logger.add_log(f"Updating existing secret for user {user_id}", logging.INFO)
                existing_wallets.append(wallet)
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f'users/{user_id}/wallets',
                    secret={'wallets': existing_wallets},
                    mount_point='secret',
                )

            # Verify that the secret was written correctly
            written_wallets = self.get_wallet(user_id)
            if written_wallets == existing_wallets and written_wallets is not None:
                self.logger.add_log(f"Successfully wrote wallets for user {user_id}", logging.INFO)
            else:
                raise Exception(f"Failed to write wallets for user {user_id}")

        except Exception as e:
            raise e  # Re-raise the exception to propagate the error

    def delete_wallet(self, user_id: str, wallet: dict):
        try:
            existing_wallets = self.get_wallet(user_id) or []
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

            # Verify that the secret was deleted correctly
            wallets_after_delete = self.get_wallet(user_id)
            if wallets_after_delete is None or wallet not in wallets_after_delete:
                self.logger.add_log(f"Successfully deleted wallet for user {user_id}", logging.INFO)
            else:
                raise Exception(f"Failed to delete wallet for user {user_id}")

        except Exception as e:
            raise e  # Re-raise the exception to propagate the error

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
                wallets = read_response['data']['data'].get('wallets', [])
                self.logger.add_log(f"No wallets found for user {user_id}", logging.DEBUG)
                return wallets
            else:
                self.logger.add_log(f"No wallets found for user {user_id}", logging.DEBUG)
                return None
        except hvac.exceptions.InvalidPath:
            self.logger.add_log(f"No data found in Vault for user {user_id}", logging.WARNING)
            return None
        except Exception as e:
            self.logger.add_log(f"Error during wallet retrieval for user {user_id}: {e}", logging.ERROR)
            return None
