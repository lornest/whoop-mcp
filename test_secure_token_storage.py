import json
import os
import time
from pathlib import Path
from unittest.mock import patch
import tempfile
import shutil

import pytest
from cryptography.fernet import Fernet

from secure_token_storage import (
    TokenData,
    KeyringTokenStorage,
    EncryptedFileTokenStorage,
    SecureTokenStorage,
    get_storage_backend,
    KEYRING_SERVICE,
    KEYRING_USERNAME,
)


# ==============================================================================
# TokenData Tests
# ==============================================================================

class TestTokenData:
    """Test suite for TokenData dataclass."""

    def test_token_data_creation_with_all_fields(self):
        """Test creating TokenData with all fields populated."""
        access_token = "test_access_token"
        refresh_token = "test_refresh_token"
        client_id = "test_client_id"
        client_secret = "test_client_secret"
        expires_at = time.time() + 3600
        created_at = time.time()

        token_data = TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            expires_at=expires_at,
            created_at=created_at
        )

        assert token_data.access_token == access_token
        assert token_data.refresh_token == refresh_token
        assert token_data.client_id == client_id
        assert token_data.client_secret == client_secret
        assert token_data.expires_at == expires_at
        assert token_data.created_at == created_at

    def test_token_data_creation_with_optional_fields_none(self):
        """Test creating TokenData with optional fields as None."""
        access_token = "test_access_token"
        client_id = "test_client_id"
        client_secret = "test_client_secret"
        created_at = time.time()

        token_data = TokenData(
            access_token=access_token,
            refresh_token=None,
            client_id=client_id,
            client_secret=client_secret,
            expires_at=None,
            created_at=created_at
        )

        assert token_data.access_token == access_token
        assert token_data.refresh_token is None
        assert token_data.client_id == client_id
        assert token_data.client_secret == client_secret
        assert token_data.expires_at is None
        assert token_data.created_at == created_at

    def test_token_data_equality(self):
        """Test TokenData equality comparison."""
        created_at = time.time()
        token_data1 = TokenData(
            access_token="token",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=created_at
        )
        token_data2 = TokenData(
            access_token="token",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=created_at
        )

        assert token_data1 == token_data2

    def test_token_data_inequality(self):
        """Test TokenData inequality when fields differ."""
        created_at = time.time()
        token_data1 = TokenData(
            access_token="token1",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=created_at
        )
        token_data2 = TokenData(
            access_token="token2",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=created_at
        )

        assert token_data1 != token_data2


# ==============================================================================
# KeyringTokenStorage Tests
# ==============================================================================

class TestKeyringTokenStorage:
    """Test suite for KeyringTokenStorage."""

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time()
        )

    @pytest.fixture
    def storage(self):
        """Fixture providing KeyringTokenStorage instance."""
        return KeyringTokenStorage()

    def test_save_tokens_success(self, storage, token_data):
        """Test saving tokens to keyring successfully."""
        with patch('secure_token_storage.keyring.set_password') as mock_set:
            storage.save_tokens(token_data)

            mock_set.assert_called_once()
            call_args = mock_set.call_args
            assert call_args[0][0] == KEYRING_SERVICE
            assert call_args[0][1] == KEYRING_USERNAME

            # Verify JSON structure
            saved_json = call_args[0][2]
            saved_dict = json.loads(saved_json)
            assert saved_dict["access_token"] == token_data.access_token
            assert saved_dict["refresh_token"] == token_data.refresh_token
            assert saved_dict["client_id"] == token_data.client_id
            assert saved_dict["client_secret"] == token_data.client_secret
            assert saved_dict["expires_at"] == token_data.expires_at
            assert saved_dict["created_at"] == token_data.created_at

    def test_save_tokens_with_none_optional_fields(self, storage):
        """Test saving tokens with None optional fields."""
        token_data = TokenData(
            access_token="token",
            refresh_token=None,
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=time.time()
        )

        with patch('secure_token_storage.keyring.set_password') as mock_set:
            storage.save_tokens(token_data)

            saved_json = mock_set.call_args[0][2]
            saved_dict = json.loads(saved_json)
            assert saved_dict["refresh_token"] is None
            assert saved_dict["expires_at"] is None

    def test_save_tokens_keyring_exception(self, storage, token_data):
        """Test save_tokens raises exception when keyring fails."""
        with patch('secure_token_storage.keyring.set_password') as mock_set:
            mock_set.side_effect = Exception("Keyring error")

            with pytest.raises(Exception, match="Keyring error"):
                storage.save_tokens(token_data)

    def test_load_tokens_success(self, storage, token_data):
        """Test loading tokens from keyring successfully."""
        token_json = json.dumps({
            "access_token": token_data.access_token,
            "refresh_token": token_data.refresh_token,
            "client_id": token_data.client_id,
            "client_secret": token_data.client_secret,
            "expires_at": token_data.expires_at,
            "created_at": token_data.created_at
        })

        with patch('secure_token_storage.keyring.get_password') as mock_get:
            mock_get.return_value = token_json

            loaded_data = storage.load_tokens()

            mock_get.assert_called_once_with(KEYRING_SERVICE, KEYRING_USERNAME)
            assert loaded_data is not None
            assert loaded_data.access_token == token_data.access_token
            assert loaded_data.refresh_token == token_data.refresh_token
            assert loaded_data.client_id == token_data.client_id
            assert loaded_data.client_secret == token_data.client_secret
            assert loaded_data.expires_at == token_data.expires_at
            assert loaded_data.created_at == token_data.created_at

    def test_load_tokens_no_tokens_found(self, storage):
        """Test load_tokens returns None when no tokens exist."""
        with patch('secure_token_storage.keyring.get_password') as mock_get:
            mock_get.return_value = None

            loaded_data = storage.load_tokens()

            assert loaded_data is None

    def test_load_tokens_missing_created_at_defaults_to_current_time(self, storage):
        """Test load_tokens defaults created_at when missing."""
        token_json = json.dumps({
            "access_token": "token",
            "refresh_token": "refresh",
            "client_id": "client",
            "client_secret": "secret",
            "expires_at": time.time() + 3600
            # created_at missing
        })

        with patch('secure_token_storage.keyring.get_password') as mock_get:
            with patch('secure_token_storage.time.time') as mock_time:
                mock_get.return_value = token_json
                mock_time.return_value = 1234567890.0

                loaded_data = storage.load_tokens()

                assert loaded_data.created_at == 1234567890.0

    def test_load_tokens_invalid_json(self, storage):
        """Test load_tokens returns None when JSON is invalid."""
        with patch('secure_token_storage.keyring.get_password') as mock_get:
            mock_get.return_value = "invalid json {"

            loaded_data = storage.load_tokens()

            assert loaded_data is None

    def test_load_tokens_missing_required_fields(self, storage):
        """Test load_tokens returns None when required fields are missing."""
        token_json = json.dumps({
            "access_token": "token",
            # missing other required fields
        })

        with patch('secure_token_storage.keyring.get_password') as mock_get:
            mock_get.return_value = token_json

            loaded_data = storage.load_tokens()

            assert loaded_data is None

    def test_load_tokens_keyring_exception(self, storage):
        """Test load_tokens returns None when keyring raises exception."""
        with patch('secure_token_storage.keyring.get_password') as mock_get:
            mock_get.side_effect = Exception("Keyring error")

            loaded_data = storage.load_tokens()

            assert loaded_data is None

    def test_delete_tokens_success(self, storage):
        """Test deleting tokens from keyring successfully."""
        with patch('secure_token_storage.keyring.delete_password') as mock_delete:
            storage.delete_tokens()

            mock_delete.assert_called_once_with(KEYRING_SERVICE, KEYRING_USERNAME)

    def test_delete_tokens_no_password_to_delete(self, storage):
        """Test delete_tokens handles PasswordDeleteError gracefully."""
        with patch('secure_token_storage.keyring.delete_password') as mock_delete:
            with patch('secure_token_storage.keyring.errors.PasswordDeleteError', Exception):
                mock_delete.side_effect = Exception("Password not found")

                storage.delete_tokens()

                mock_delete.assert_called_once()

    def test_delete_tokens_general_exception(self, storage):
        """Test delete_tokens handles general exceptions gracefully."""
        with patch('secure_token_storage.keyring.delete_password') as mock_delete:
            mock_delete.side_effect = RuntimeError("Unexpected error")

            storage.delete_tokens()

            mock_delete.assert_called_once()

    def test_is_available_success(self, storage):
        """Test is_available returns True when keyring works."""
        with patch('secure_token_storage.keyring.set_password') as mock_set, \
             patch('secure_token_storage.keyring.get_password') as mock_get, \
             patch('secure_token_storage.keyring.delete_password') as mock_delete:

            mock_get.return_value = "test"

            result = storage.is_available()

            assert result is True
            mock_set.assert_called_once_with(KEYRING_SERVICE, "_test", "test")
            mock_get.assert_called_once_with(KEYRING_SERVICE, "_test")
            mock_delete.assert_called_once_with(KEYRING_SERVICE, "_test")

    def test_is_available_keyring_fails(self, storage):
        """Test is_available returns False when keyring fails."""
        with patch('secure_token_storage.keyring.set_password') as mock_set:
            mock_set.side_effect = Exception("Keyring not available")

            result = storage.is_available()

            assert result is False

    def test_is_available_test_value_mismatch(self, storage):
        """Test is_available returns False when test value doesn't match."""
        with patch('secure_token_storage.keyring.set_password') as mock_set, \
             patch('secure_token_storage.keyring.get_password') as mock_get, \
             patch('secure_token_storage.keyring.delete_password') as mock_delete:

            mock_get.return_value = "wrong_value"

            result = storage.is_available()

            assert result is False


# ==============================================================================
# EncryptedFileTokenStorage Tests
# ==============================================================================

class TestEncryptedFileTokenStorage:
    """Test suite for EncryptedFileTokenStorage."""

    @pytest.fixture
    def temp_dir(self):
        """Fixture providing temporary directory for test files."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # Cleanup
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def storage(self, temp_dir):
        """Fixture providing EncryptedFileTokenStorage instance with temp paths."""
        storage = EncryptedFileTokenStorage()
        # Override paths to use temp directory
        storage.file_path = temp_dir / "tokens.enc"
        storage.salt_path = temp_dir / "salt"
        return storage

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time()
        )

    def test_init_creates_directory(self, temp_dir):
        """Test initialization creates storage directory."""
        storage_dir = temp_dir / "new_storage"

        with patch('secure_token_storage.ENCRYPTED_FILE_DIR', storage_dir):
            storage = EncryptedFileTokenStorage()

            assert storage_dir.exists()
            # Check permissions (on Unix-like systems)
            if os.name != 'nt':
                assert oct(storage_dir.stat().st_mode)[-3:] == '700'

    def test_get_encryption_key_creates_new_salt(self, storage, temp_dir):
        """Test encryption key generation creates new salt file."""
        assert not storage.salt_path.exists()

        key = storage._get_encryption_key()

        assert storage.salt_path.exists()
        assert len(key) > 0
        # Check salt file permissions
        if os.name != 'nt':
            assert oct(storage.salt_path.stat().st_mode)[-3:] == '600'

    def test_get_encryption_key_reuses_existing_salt(self, storage, temp_dir):
        """Test encryption key generation reuses existing salt."""
        original_salt = os.urandom(16)
        storage.salt_path.write_bytes(original_salt)

        key1 = storage._get_encryption_key()
        key2 = storage._get_encryption_key()

        assert key1 == key2
        assert storage.salt_path.read_bytes() == original_salt

    def test_get_encryption_key_deterministic_with_same_salt(self, storage):
        """Test encryption key is deterministic with same salt."""
        # Arrange & Act
        key1 = storage._get_encryption_key()
        key2 = storage._get_encryption_key()

        assert key1 == key2

    def test_get_encryption_key_handles_uuid_exception(self, storage, temp_dir):
        """Test encryption key generation handles uuid.getnode() failure."""
        with patch('secure_token_storage.uuid.getnode') as mock_getnode:
            mock_getnode.side_effect = Exception("UUID error")

            key = storage._get_encryption_key()

            assert len(key) > 0  # Should still generate a key with fallback

    def test_save_tokens_success(self, storage, token_data):
        """Test saving tokens to encrypted file successfully."""
        storage.save_tokens(token_data)

        assert storage.file_path.exists()
        # Check file permissions
        if os.name != 'nt':
            assert oct(storage.file_path.stat().st_mode)[-3:] == '600'

        # Verify file is encrypted (not plain JSON)
        encrypted_content = storage.file_path.read_bytes()
        assert b"access_token" not in encrypted_content

    def test_save_tokens_with_none_optional_fields(self, storage):
        """Test saving tokens with None optional fields."""
        token_data = TokenData(
            access_token="token",
            refresh_token=None,
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=time.time()
        )

        storage.save_tokens(token_data)

        assert storage.file_path.exists()

    def test_save_tokens_overwrites_existing_file(self, storage, token_data):
        """Test saving tokens overwrites existing encrypted file."""
        storage.file_path.write_bytes(b"old encrypted data")

        storage.save_tokens(token_data)

        # Should be able to load the new data
        loaded_data = storage.load_tokens()
        assert loaded_data.access_token == token_data.access_token

    def test_save_tokens_encryption_failure(self, storage, token_data):
        """Test save_tokens raises exception on encryption failure."""
        with patch.object(storage, '_get_encryption_key') as mock_key:
            mock_key.side_effect = Exception("Encryption error")

            with pytest.raises(Exception, match="Encryption error"):
                storage.save_tokens(token_data)

    def test_load_tokens_success(self, storage, token_data):
        """Test loading tokens from encrypted file successfully."""
        storage.save_tokens(token_data)

        loaded_data = storage.load_tokens()

        assert loaded_data is not None
        assert loaded_data.access_token == token_data.access_token
        assert loaded_data.refresh_token == token_data.refresh_token
        assert loaded_data.client_id == token_data.client_id
        assert loaded_data.client_secret == token_data.client_secret
        assert loaded_data.expires_at == token_data.expires_at
        assert loaded_data.created_at == token_data.created_at

    def test_load_tokens_file_does_not_exist(self, storage):
        """Test load_tokens returns None when file doesn't exist."""
        loaded_data = storage.load_tokens()

        assert loaded_data is None

    def test_load_tokens_corrupted_encrypted_data(self, storage):
        """Test load_tokens returns None with corrupted encrypted data."""
        storage.file_path.write_bytes(b"corrupted encrypted data")

        loaded_data = storage.load_tokens()

        assert loaded_data is None

    def test_load_tokens_invalid_json_after_decryption(self, storage):
        """Test load_tokens returns None when decrypted data is invalid JSON."""
        fernet = Fernet(storage._get_encryption_key())
        encrypted_invalid_json = fernet.encrypt(b"invalid json {")
        storage.file_path.write_bytes(encrypted_invalid_json)

        loaded_data = storage.load_tokens()

        assert loaded_data is None

    def test_load_tokens_missing_required_fields(self, storage):
        """Test load_tokens returns None when required fields are missing."""
        incomplete_token = {
            "access_token": "token"
            # missing other required fields
        }
        fernet = Fernet(storage._get_encryption_key())
        encrypted_data = fernet.encrypt(json.dumps(incomplete_token).encode())
        storage.file_path.write_bytes(encrypted_data)

        loaded_data = storage.load_tokens()

        assert loaded_data is None

    def test_load_tokens_missing_created_at_defaults_to_current_time(self, storage):
        """Test load_tokens defaults created_at when missing."""
        token_dict = {
            "access_token": "token",
            "refresh_token": "refresh",
            "client_id": "client",
            "client_secret": "secret",
            "expires_at": time.time() + 3600
            # created_at missing
        }
        fernet = Fernet(storage._get_encryption_key())
        encrypted_data = fernet.encrypt(json.dumps(token_dict).encode())
        storage.file_path.write_bytes(encrypted_data)

        with patch('secure_token_storage.time.time') as mock_time:
            mock_time.return_value = 1234567890.0

            loaded_data = storage.load_tokens()

            assert loaded_data.created_at == 1234567890.0

    def test_load_tokens_wrong_encryption_key(self, storage, token_data):
        """Test load_tokens returns None when encryption key changes."""
        storage.save_tokens(token_data)

        # Change the salt to simulate wrong key
        storage.salt_path.write_bytes(os.urandom(16))

        loaded_data = storage.load_tokens()

        assert loaded_data is None

    def test_delete_tokens_success(self, storage, token_data):
        """Test deleting encrypted token file successfully."""
        storage.save_tokens(token_data)
        assert storage.file_path.exists()

        storage.delete_tokens()

        assert not storage.file_path.exists()

    def test_delete_tokens_file_does_not_exist(self, storage):
        """Test delete_tokens handles non-existent file gracefully."""
        # Act (should not raise)
        storage.delete_tokens()

        assert not storage.file_path.exists()

    def test_delete_tokens_permission_error(self, storage, token_data):
        """Test delete_tokens handles permission errors gracefully."""
        storage.save_tokens(token_data)

        with patch.object(Path, 'unlink') as mock_unlink:
            mock_unlink.side_effect = PermissionError("Permission denied")

            storage.delete_tokens()

            mock_unlink.assert_called_once()

    def test_is_available_always_returns_true(self, storage):
        """Test is_available always returns True for file storage."""
        result = storage.is_available()

        assert result is True

    def test_round_trip_save_and_load(self, storage, token_data):
        """Test complete round-trip of saving and loading tokens."""
        storage.save_tokens(token_data)
        loaded_data = storage.load_tokens()

        assert loaded_data == token_data

    def test_encryption_key_is_url_safe_base64(self, storage):
        """Test encryption key is valid URL-safe base64."""
        key = storage._get_encryption_key()

        # Should not raise exception
        Fernet(key)


# ==============================================================================
# get_storage_backend() Tests
# ==============================================================================

class TestGetStorageBackend:
    """Test suite for get_storage_backend() function."""

    def test_returns_keyring_when_available(self):
        """Test get_storage_backend returns KeyringTokenStorage when available."""
        with patch.object(KeyringTokenStorage, 'is_available', return_value=True):
            backend = get_storage_backend()

            assert isinstance(backend, KeyringTokenStorage)

    def test_returns_encrypted_file_when_keyring_unavailable(self):
        """Test get_storage_backend returns EncryptedFileTokenStorage as fallback."""
        with patch.object(KeyringTokenStorage, 'is_available', return_value=False):
            backend = get_storage_backend()

            assert isinstance(backend, EncryptedFileTokenStorage)

    def test_returns_secure_token_storage_instance(self):
        """Test get_storage_backend returns SecureTokenStorage interface."""
        backend = get_storage_backend()

        assert isinstance(backend, SecureTokenStorage)
        assert hasattr(backend, 'save_tokens')
        assert hasattr(backend, 'load_tokens')
        assert hasattr(backend, 'delete_tokens')
        assert hasattr(backend, 'is_available')

    def test_backend_selection_logs_correctly(self):
        """Test get_storage_backend logs the selected backend."""
        with patch.object(KeyringTokenStorage, 'is_available', return_value=True):
            with patch('secure_token_storage.logger.info') as mock_log:
                backend = get_storage_backend()

                assert isinstance(backend, KeyringTokenStorage)
                # Should have logged keyring selection
                mock_log.assert_called()


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestStorageIntegration:
    """Integration tests for storage backends."""

    @pytest.fixture
    def temp_dir(self):
        """Fixture providing temporary directory for test files."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # Cleanup
        if temp_path.exists():
            shutil.rmtree(temp_path)

    def test_multiple_save_and_load_operations(self, temp_dir):
        """Test multiple sequential save/load operations."""
        storage = EncryptedFileTokenStorage()
        storage.file_path = temp_dir / "tokens.enc"
        storage.salt_path = temp_dir / "salt"

        token_data1 = TokenData(
            access_token="token1",
            refresh_token="refresh1",
            client_id="client1",
            client_secret="secret1",
            expires_at=time.time() + 3600,
            created_at=time.time()
        )
        token_data2 = TokenData(
            access_token="token2",
            refresh_token="refresh2",
            client_id="client2",
            client_secret="secret2",
            expires_at=time.time() + 7200,
            created_at=time.time()
        )

        storage.save_tokens(token_data1)
        loaded1 = storage.load_tokens()
        assert loaded1 == token_data1

        storage.save_tokens(token_data2)
        loaded2 = storage.load_tokens()
        assert loaded2 == token_data2
        assert loaded2 != token_data1

    def test_delete_and_reload_returns_none(self, temp_dir):
        """Test loading after deletion returns None."""
        storage = EncryptedFileTokenStorage()
        storage.file_path = temp_dir / "tokens.enc"
        storage.salt_path = temp_dir / "salt"

        token_data = TokenData(
            access_token="token",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=time.time()
        )

        storage.save_tokens(token_data)
        assert storage.load_tokens() is not None

        storage.delete_tokens()
        loaded = storage.load_tokens()

        assert loaded is None

    def test_concurrent_backend_selection(self):
        """Test get_storage_backend returns consistent backend type."""
        backend1 = get_storage_backend()
        backend2 = get_storage_backend()

        assert type(backend1) == type(backend2)


# ==============================================================================
# Edge Cases and Boundary Conditions
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_token_data_with_empty_strings(self):
        """Test TokenData accepts empty strings."""
        token_data = TokenData(
            access_token="",
            refresh_token="",
            client_id="",
            client_secret="",
            expires_at=None,
            created_at=0.0
        )

        assert token_data.access_token == ""
        assert token_data.refresh_token == ""

    def test_token_data_with_very_long_strings(self):
        """Test TokenData handles very long strings."""
        long_string = "a" * 10000

        token_data = TokenData(
            access_token=long_string,
            refresh_token=long_string,
            client_id=long_string,
            client_secret=long_string,
            expires_at=None,
            created_at=time.time()
        )

        assert len(token_data.access_token) == 10000

    def test_token_data_with_special_characters(self):
        """Test TokenData handles special characters in strings."""
        special_string = "token!@#$%^&*(){}[]|\\:;\"'<>,.?/~`"

        token_data = TokenData(
            access_token=special_string,
            refresh_token=special_string,
            client_id=special_string,
            client_secret=special_string,
            expires_at=None,
            created_at=time.time()
        )

        assert token_data.access_token == special_string

    def test_token_data_with_unicode_characters(self):
        """Test TokenData handles unicode characters."""
        unicode_string = "token_日本語_émojis_🎉🎊"

        token_data = TokenData(
            access_token=unicode_string,
            refresh_token=unicode_string,
            client_id=unicode_string,
            client_secret=unicode_string,
            expires_at=None,
            created_at=time.time()
        )

        assert token_data.access_token == unicode_string

    def test_token_data_with_negative_timestamps(self):
        """Test TokenData handles negative timestamps."""
        token_data = TokenData(
            access_token="token",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=-1000.0,
            created_at=-2000.0
        )

        assert token_data.expires_at == -1000.0
        assert token_data.created_at == -2000.0

    def test_token_data_with_very_large_timestamps(self):
        """Test TokenData handles very large timestamps."""
        large_timestamp = 9999999999.999999

        token_data = TokenData(
            access_token="token",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=large_timestamp,
            created_at=large_timestamp
        )

        assert token_data.expires_at == large_timestamp

    @pytest.fixture
    def temp_dir(self):
        """Fixture providing temporary directory."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        if temp_path.exists():
            shutil.rmtree(temp_path)

    def test_encrypted_storage_with_unicode_tokens(self, temp_dir):
        """Test encrypted storage handles unicode in tokens."""
        storage = EncryptedFileTokenStorage()
        storage.file_path = temp_dir / "tokens.enc"
        storage.salt_path = temp_dir / "salt"

        token_data = TokenData(
            access_token="token_日本語_🎉",
            refresh_token="refresh_émojis_🎊",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=time.time()
        )

        storage.save_tokens(token_data)
        loaded_data = storage.load_tokens()

        assert loaded_data.access_token == token_data.access_token
        assert loaded_data.refresh_token == token_data.refresh_token

    def test_keyring_storage_with_unicode_tokens(self):
        """Test keyring storage handles unicode in tokens."""
        storage = KeyringTokenStorage()
        token_data = TokenData(
            access_token="token_日本語_🎉",
            refresh_token="refresh_émojis_🎊",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=time.time()
        )

        with patch('secure_token_storage.keyring.set_password') as mock_set, \
             patch('secure_token_storage.keyring.get_password') as mock_get:

            # Capture what was saved
            saved_data = None
            def capture_save(_service, _username, data):
                nonlocal saved_data
                saved_data = data

            mock_set.side_effect = capture_save
            mock_get.return_value = None  # Will be set after save

            storage.save_tokens(token_data)

            # Setup mock to return saved data
            mock_get.return_value = saved_data
            loaded_data = storage.load_tokens()

            assert loaded_data.access_token == token_data.access_token
            assert loaded_data.refresh_token == token_data.refresh_token
