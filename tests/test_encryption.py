"""
Test suite for encryption utils
"""
import pytest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.encryption import (
    encrypt_password, decrypt_password,
    _get_encryption_key, _ENCRYPTION_KEY
)


class TestEncryption:
    """Test cases for encryption utils"""

    def setup_method(self):
        """Clear cached key before each test"""
        global _ENCRYPTION_KEY
        _ENCRYPTION_KEY = None
        if "ENCRYPTION_KEY" in os.environ:
            del os.environ["ENCRYPTION_KEY"]

    def test_encrypt_decrypt_password(self):
        """Test basic encrypt and decrypt functionality"""
        original = "TestPassword123!"
        encrypted = encrypt_password(original)
        
        assert encrypted != original
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string(self):
        """Test encrypting empty string"""
        result = encrypt_password("")
        assert result == ""

    def test_encrypt_none(self):
        """Test encrypting None"""
        result = encrypt_password(None)
        assert result == ""

    def test_decrypt_empty_string(self):
        """Test decrypting empty string"""
        result = decrypt_password("")
        assert result == ""

    def test_decrypt_none(self):
        """Test decrypting None"""
        result = decrypt_password(None)
        assert result == ""

    def test_encrypt_special_characters(self):
        """Test encrypting password with special characters"""
        original = "P@ssw0rd!#$%^&*()_+-=[]{}|;:,.<>?"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_encrypt_unicode(self):
        """Test encrypting password with unicode characters"""
        original = "密码🚀test中文"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_multiple_encrypt_decrypt(self):
        """Test multiple encrypt/decrypt cycles"""
        passwords = [
            "SimplePass123",
            "C0mpl3x!P@ssw0rd#",
            "Unicode测试🌟",
            "VeryLongPassword" * 10,
        ]
        
        for pwd in passwords:
            encrypted = encrypt_password(pwd)
            decrypted = decrypt_password(encrypted)
            assert decrypted == pwd

    @patch('app.utils.encryption.Fernet')
    @patch('os.getenv')
    def test_get_encryption_key_from_env(self, mock_getenv, mock_fernet):
        """Test getting encryption key from environment variable"""
        global _ENCRYPTION_KEY
        _ENCRYPTION_KEY = None
        
        mock_fernet.generate_key.return_value = b'12345678901234567890123456789012'
        mock_fernet.return_value = MagicMock()
        
        mock_getenv.return_value = "12345678901234567890123456789012"
        
        key = _get_encryption_key()
        assert key is not None
        assert isinstance(key, bytes)

    def test_test_encryption_success(self):
        """Test encryption/decryption workflow"""
        # Test the workflow directly
        original = "TestPassword123!"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert original == decrypted

    def test_encrypt_decrypt_integration(self):
        """Integration test for encrypt/decrypt workflow"""
        passwords = [
            "user1_password",
            "admin@123",
            "root!@#$%",
        ]
        
        for pwd in passwords:
            encrypted = encrypt_password(pwd)
            decrypted = decrypt_password(encrypted)
            assert decrypted == pwd


class TestEncryptionErrorCases:
    """Test error cases for encryption"""

    def test_decrypt_invalid_token(self):
        """Test decrypting invalid token raises ValueError"""
        with pytest.raises(ValueError):
            decrypt_password("invalid-token-that-is-not-valid-fernet-token")

    @patch('app.utils.encryption.Fernet')
    def test_encrypt_exception(self, mock_fernet):
        """Test encrypt_password handles exceptions"""
        mock_instance = MagicMock()
        mock_instance.encrypt.side_effect = Exception("Encryption failed")
        mock_fernet.return_value = mock_instance
        
        with pytest.raises(ValueError):
            encrypt_password("test")

    @patch('app.utils.encryption.Fernet')
    def test_decrypt_exception(self, mock_fernet):
        """Test decrypt_password handles exceptions"""
        mock_instance = MagicMock()
        mock_instance.decrypt.side_effect = Exception("Decryption failed")
        mock_fernet.return_value = mock_instance
        
        with pytest.raises(ValueError):
            decrypt_password("some-encrypted-token")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
