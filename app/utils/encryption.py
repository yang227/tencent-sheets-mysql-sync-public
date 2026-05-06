"""
加密工具模块 - 使用 AES-256 (Fernet) 对敏感信息进行加密和解密
"""
from cryptography.fernet import Fernet
from cryptography.exceptions import InvalidKey
import base64
import logging

logger = logging.getLogger(__name__)

# 从环境变量或配置中读取密钥，这里使用固定密钥作为示例
# 生产环境应从安全的地方获取密钥（如环境变量、密钥管理服务）
_ENCRYPTION_KEY = None


def _get_encryption_key() -> bytes:
    """获取或生成加密密钥"""
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        import os
        key_str = os.getenv("ENCRYPTION_KEY")
        if key_str:
            # 使用提供的密钥（需要是 Fernet 密钥格式）
            try:
                # 验证密钥格式
                Fernet(key_str.encode('utf-8'))
                _ENCRYPTION_KEY = key_str.encode('utf-8')
            except Exception:
                # 如果密钥格式不正确，重新生成
                _ENCRYPTION_KEY = Fernet.generate_key()
                logger.warning(
                    "ENCRYPTION_KEY 环境变量格式不正确，使用临时密钥！"
                    "请设置正确的 ENCRYPTION_KEY 环境变量。生成的密钥: %s",
                    _ENCRYPTION_KEY.decode('utf-8')
                )
        else:
            # 生成新密钥并警告
            _ENCRYPTION_KEY = Fernet.generate_key()
            logger.warning(
                "使用临时加密密钥！请设置 ENCRYPTION_KEY 环境变量以获得持久化加密。"
                "生成的密钥（请保存到环境变量中）: %s",
                _ENCRYPTION_KEY.decode('utf-8')
            )
    return _ENCRYPTION_KEY


def encrypt_password(password: str) -> str:
    """
    加密密码或敏感信息
    
    Args:
        password: 明文密码或敏感信息
        
    Returns:
        加密后的字符串（base64编码）
    """
    if not password:
        return ""
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(password.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"加密失败: {e}")
        raise ValueError(f"加密失败: {e}")


def decrypt_password(encrypted_password: str) -> str:
    """
    解密密码或敏感信息
    
    Args:
        encrypted_password: 加密后的字符串（Fernet token）
        
    Returns:
        解密后的明文密码或敏感信息
    """
    if not encrypted_password:
        return ""
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_password.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidKey:
        logger.error("解密密钥无效")
        raise ValueError("解密密钥无效，无法解密密码")
    except Exception as e:
        logger.error(f"解密失败: {e}")
        raise ValueError(f"解密失败: {e}")


def test_encryption() -> bool:
    """测试加密解密功能是否正常"""
    try:
        test_str = "TestPassword123!"
        encrypted = encrypt_password(test_str)
        decrypted = decrypt_password(encrypted)
        return test_str == decrypted
    except Exception as e:
        logger.error(f"加密测试失败: {e}")
        return False
