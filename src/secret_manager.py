# secrets_manager.py
import logging
from typing import Optional
import hvac


class SecretsManager:
    def __init__(self, url: str, token: str, logger):
        self.client = hvac.Client(url=url, token=token)
        self.logger = logger

        if self.client.is_authenticated():
            token = self.client.lookup_token()['data']
            self.logger.add_log(f"Successfully authenticated in Vault as {token['display_name']}", logging.INFO)
        else:
            self.logger.add_log(f"Failed to authenticate with Vault", logging.ERROR)
            raise Exception('Failed to authenticate with Vault')

    def store_wallet(self, user_id: str, wallet: dict):
        try:
            existing_wallets = self.get_wallet(user_id)
            if existing_wallets is None:
                # No existing wallets, create new secret
                self.logger.add_log(f"Creating new secret for user {user_id}", logging.INFO)
                self.client.secrets.kv.v1.create_or_update_secret(
                    path=f'users/{user_id}/wallets',
                    secret={'wallets': [wallet]},
                    mount_point='secret',
                )
            else:
                # Existing wallets found, append new wallet and update secret
                self.logger.add_log(f"Updating existing secret for user {user_id}", logging.INFO)
                existing_wallets.append(wallet)
                self.client.secrets.kv.v1.create_or_update_secret(
                    path=f'users/{user_id}/wallets',
                    secret={'wallets': existing_wallets},
                    mount_point='secret',
                )

        except Exception as e:
            self.logger.add_log(f"Error during wallet storage for user {user_id}: {str(e)}", logging.ERROR)
            raise e

    def delete_wallet(self, user_id: str, wallet: dict):
        try:
            existing_wallets = self.get_wallet(user_id) or []
            if wallet in existing_wallets:
                existing_wallets.remove(wallet)
                if existing_wallets:
                    # If there are other wallets, overwrite with the updated list
                    self.client.secrets.kv.v1.create_or_update_secret(
                        path=f'users/{user_id}/wallets',
                        secret={'wallets': existing_wallets},
                        mount_point='secret',
                    )
                else:
                    # If there are no other wallets, delete the secret
                    self.client.secrets.kv.v1.delete_secret(
                        path=f'users/{user_id}/wallets',
                        mount_point='secret',
                    )

        except Exception as e:
            self.logger.add_log(f"Error during wallet deletion for user {user_id}: {str(e)}", logging.ERROR)
            raise e

    def get_wallet(self, user_id: str) -> Optional[list]:
        try:
            # Proceed with retrieval.
            read_response = self.client.secrets.kv.v1.read_secret(
                path=f'users/{user_id}/wallets',
                mount_point='secret',
            )
            if read_response and 'data' in read_response:
                wallets = read_response['data'].get('wallets', [])
                if wallets:
                    self.logger.add_log(f"Retrieved wallets for user {user_id}", logging.DEBUG)
                    return wallets
                else:
                    self.logger.add_log(f"No wallets found for user {user_id}", logging.DEBUG)
                    return None
            else:
                self.logger.add_log(f"No wallets found for user {user_id}", logging.DEBUG)
                return None
        except hvac.exceptions.InvalidPath:
            self.logger.add_log(f"No data found in Vault for user {user_id}", logging.WARNING)
            return None
        except Exception as e:
            self.logger.add_log(f"Error during wallet retrieval for user {user_id}: {str(e)}", logging.ERROR)
            return None
