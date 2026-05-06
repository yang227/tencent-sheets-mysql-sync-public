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


class SyncConfig(BaseModel):
    default_poll_interval: int = 30
    batch_size: int = 100
    retry_times: int = 3


class Settings(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    tencent: TencentConfig = TencentConfig()
    app: AppConfig = AppConfig()
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
