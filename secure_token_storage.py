"""
Secure Token Storage

Provides secure storage for OAuth tokens using OS keychain
or encrypted file storage, following MCP security best practices.
"""

import base64
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "whoop-mcp-tokens"
KEYRING_USERNAME = "default"
ENCRYPTED_FILE_DIR = Path.home() / ".whoop_mcp"
ENCRYPTED_FILE_PATH = ENCRYPTED_FILE_DIR / "tokens.enc"
SALT_FILE_PATH = ENCRYPTED_FILE_DIR / "salt"


@dataclass
class TokenData:
    """OAuth token data structure."""

    access_token: str
    refresh_token: str | None
    client_id: str
    client_secret: str
    expires_at: float | None  # Unix timestamp
    created_at: float


class SecureTokenStorage(ABC):
    """Abstract base class for token storage backends."""

    @abstractmethod
    def save_tokens(self, token_data: TokenData) -> None:
        """Save tokens to secure storage."""
        pass

    @abstractmethod
    def load_tokens(self) -> TokenData | None:
        """Load tokens from secure storage."""
        pass

    @abstractmethod
    def delete_tokens(self) -> None:
        """Delete stored tokens."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this storage backend is available."""
        pass


class KeyringTokenStorage(SecureTokenStorage):
    """OS keychain-based secure token storage."""

    def save_tokens(self, token_data: TokenData) -> None:
        """Save tokens to OS keychain."""
        try:
            token_json = json.dumps(
                {
                    "access_token": token_data.access_token,
                    "refresh_token": token_data.refresh_token,
                    "client_id": token_data.client_id,
                    "client_secret": token_data.client_secret,
                    "expires_at": token_data.expires_at,
                    "created_at": token_data.created_at,
                }
            )
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token_json)
            logger.info("Tokens saved to OS keychain")
        except Exception as e:
            logger.error(f"Failed to save tokens to keyring: {e}")
            raise

    def load_tokens(self) -> TokenData | None:
        """Load tokens from OS keychain."""
        try:
            token_json = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if not token_json:
                logger.info("No tokens found in OS keychain")
                return None

            token_dict = json.loads(token_json)
            return TokenData(
                access_token=token_dict["access_token"],
                refresh_token=token_dict.get("refresh_token"),
                client_id=token_dict["client_id"],
                client_secret=token_dict["client_secret"],
                expires_at=token_dict.get("expires_at"),
                created_at=token_dict.get("created_at", time.time()),
            )
        except Exception as e:
            logger.error(f"Failed to load tokens from keyring: {e}")
            return None

    def delete_tokens(self) -> None:
        """Delete tokens from OS keychain."""
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
            logger.info("Tokens deleted from OS keychain")
        except keyring.errors.PasswordDeleteError:
            logger.info("No tokens to delete from keychain")
        except Exception as e:
            logger.error(f"Failed to delete tokens from keyring: {e}")

    def is_available(self) -> bool:
        """Check if keyring is available."""
        try:
            keyring.set_password(KEYRING_SERVICE, "_test", "test")
            result = keyring.get_password(KEYRING_SERVICE, "_test")
            keyring.delete_password(KEYRING_SERVICE, "_test")
            return result == "test"
        except Exception:
            return False


class EncryptedFileTokenStorage(SecureTokenStorage):
    """Encrypted file-based token storage fallback."""

    def __init__(self):
        """Initialize encrypted file storage."""
        self.file_path = ENCRYPTED_FILE_PATH
        self.salt_path = SALT_FILE_PATH
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure storage directory exists with proper permissions."""
        ENCRYPTED_FILE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _get_encryption_key(self) -> bytes:
        """Generate or load encryption key from machine UUID and salt."""
        if self.salt_path.exists():
            with open(self.salt_path, "rb") as f:
                salt = f.read()
        else:
            salt = os.urandom(16)
            with open(self.salt_path, "wb") as f:
                f.write(salt)
            os.chmod(self.salt_path, 0o600)

        try:
            machine_id = str(uuid.getnode()).encode()
        except Exception:
            machine_id = b"fallback-machine-id"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id))
        return key

    def save_tokens(self, token_data: TokenData) -> None:
        """Save encrypted tokens to file."""
        try:
            token_dict = {
                "access_token": token_data.access_token,
                "refresh_token": token_data.refresh_token,
                "client_id": token_data.client_id,
                "client_secret": token_data.client_secret,
                "expires_at": token_data.expires_at,
                "created_at": token_data.created_at,
            }
            token_json = json.dumps(token_dict).encode()

            fernet = Fernet(self._get_encryption_key())
            encrypted_data = fernet.encrypt(token_json)

            with open(self.file_path, "wb") as f:
                f.write(encrypted_data)
            os.chmod(self.file_path, 0o600)

            logger.info(f"Tokens saved to encrypted file: {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save encrypted tokens: {e}")
            raise

    def load_tokens(self) -> TokenData | None:
        """Load encrypted tokens from file."""
        try:
            if not self.file_path.exists():
                logger.info(f"No encrypted token file found at {self.file_path}")
                return None

            with open(self.file_path, "rb") as f:
                encrypted_data = f.read()

            fernet = Fernet(self._get_encryption_key())
            token_json = fernet.decrypt(encrypted_data)
            token_dict = json.loads(token_json.decode())

            return TokenData(
                access_token=token_dict["access_token"],
                refresh_token=token_dict.get("refresh_token"),
                client_id=token_dict["client_id"],
                client_secret=token_dict["client_secret"],
                expires_at=token_dict.get("expires_at"),
                created_at=token_dict.get("created_at", time.time()),
            )
        except Exception as e:
            logger.error(f"Failed to load encrypted tokens: {e}")
            return None

    def delete_tokens(self) -> None:
        """Delete encrypted token file."""
        try:
            if self.file_path.exists():
                self.file_path.unlink()
                logger.info(f"Encrypted token file deleted: {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to delete encrypted tokens: {e}")

    def is_available(self) -> bool:
        """Encrypted file storage is always available."""
        return True


def get_storage_backend() -> SecureTokenStorage:
    """
    Get the best available storage backend.

    Priority: Keyring > Encrypted File

    Returns:
        SecureTokenStorage instance
    """
    # Try keyring first
    keyring_storage = KeyringTokenStorage()
    if keyring_storage.is_available():
        logger.info("Using OS keychain for token storage")
        return keyring_storage

    # Fall back to encrypted file
    logger.info("OS keychain unavailable, using encrypted file storage")
    return EncryptedFileTokenStorage()
