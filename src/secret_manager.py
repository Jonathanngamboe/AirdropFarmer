# secrets_manager.py
import logging
from datetime import datetime
from typing import Optional
import hvac


class SecretsManager:
    _is_authenticated = False  # Class attribute to store the authentication status

    def __init__(self, url: str, token: str, logger):
        self.client = hvac.Client(url=url, token=token)
        self.logger = logger
        self.authenticate()  # Call the authenticate method during initialization

    def authenticate(self):
        # Check if already authenticated
        if not SecretsManager._is_authenticated:
            if self.client.is_authenticated():
                token = self.client.lookup_token()['data']
                self.logger.add_log(f"Successfully authenticated in Vault as {token['display_name']}", logging.INFO)
                SecretsManager._is_authenticated = True  # Update the class attribute
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
                    # self.logger.add_log(f"Retrieved wallets for user {user_id}", logging.INFO)
                    return wallets
                else:
                    # self.logger.add_log(f"No wallets found for user {user_id}", logging.INFO)
                    return None
            else:
                # self.logger.add_log(f"No wallets found for user {user_id}", logging.INFO)
                return None
        except hvac.exceptions.InvalidPath:
            return None
        except Exception as e:
            self.logger.add_log(f"Error during wallet retrieval for user {user_id}: {str(e)}", logging.ERROR)
            return None
