"""Configuration loader from config.yaml and .env"""
import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Load .env file if exists
def load_env_file():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        try:
                            key, value = line.split('=', 1)
                            os.environ.setdefault(key.strip(), value.strip())
                        except ValueError:
                            logger.warning(f"Skipping malformed line in .env: {line}")
        except IOError as e:
            logger.warning(f"Failed to read .env file: {e}")

load_env_file()


def _get_env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return int(value)

class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    name: str = "tencent_sheets_sync"


class TencentConfig(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    callback_token: str = ""
    open_id: str = ""  # 用户 Open-Id，授权后获得


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    webhook_base_url: str = "https://localhost:8080"


class FrontendConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5173
    backend_url: str = ""


class SyncConfig(BaseModel):
    default_poll_interval: int = 30
    batch_size: int = 100
    retry_times: int = 3


class Settings(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    tencent: TencentConfig = TencentConfig()
    app: AppConfig = AppConfig()
    frontend: FrontendConfig = FrontendConfig()
    sync: SyncConfig = SyncConfig()


_settings: Optional[Settings] = None


def load_config(config_path: Optional[str] = None) -> Settings:
    """Load configuration from YAML file."""
    global _settings
    
    if _settings is not None:
        return _settings
    
    if config_path is None:
        # Look for config.yaml in project root
        config_path = os.environ.get(
            "CONFIG_PATH",
            str(Path(__file__).parent.parent / "config.yaml")
        )
    
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        _settings = Settings(**config_data)
    else:
        _settings = Settings()

    _settings.database.host = _get_env_str("DATABASE_HOST", _settings.database.host)
    _settings.database.port = _get_env_int("DATABASE_PORT", _settings.database.port)
    _settings.database.user = _get_env_str("DATABASE_USER", _settings.database.user)
    _settings.database.password = _get_env_str("DATABASE_PASSWORD", _settings.database.password)
    _settings.database.name = _get_env_str("DATABASE_NAME", _settings.database.name)

    _settings.tencent.app_id = _get_env_str("TENCENT_APP_ID", _settings.tencent.app_id)
    _settings.tencent.app_secret = _get_env_str("TENCENT_APP_SECRET", _settings.tencent.app_secret)
    _settings.tencent.callback_token = _get_env_str("TENCENT_CALLBACK_TOKEN", _settings.tencent.callback_token)
    _settings.tencent.open_id = _get_env_str("TENCENT_OPEN_ID", _settings.tencent.open_id)

    _settings.app.host = _get_env_str("APP_HOST", _settings.app.host)
    _settings.app.port = _get_env_int("APP_PORT", _settings.app.port)
    _settings.app.webhook_base_url = _get_env_str("APP_WEBHOOK_BASE_URL", _settings.app.webhook_base_url)

    _settings.frontend.host = _get_env_str("FRONTEND_HOST", _settings.frontend.host)
    _settings.frontend.port = _get_env_int("FRONTEND_PORT", _settings.frontend.port)
    _settings.frontend.backend_url = _get_env_str("FRONTEND_BACKEND_URL", _settings.frontend.backend_url)
    
    return _settings


def get_settings() -> Settings:
    """Get current settings, loading if necessary."""
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


# Alias for backward compatibility
def get_config() -> Settings:
    """Alias for get_settings()."""
    return get_settings()


def reload_config(config_path: Optional[str] = None) -> Settings:
    """Force reload configuration."""
    global _settings
    _settings = None
    return load_config(config_path)
