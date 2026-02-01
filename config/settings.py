import json
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]
    
    # CryptoBot (не используется, оставлено для совместимости)
    # CRYPTOBOT_TOKEN: str = os.getenv("CRYPTOBOT_TOKEN", "")
    # CRYPTOBOT_TESTNET: bool = os.getenv("CRYPTOBOT_TESTNET", "false").lower() == "true"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/database.db")
    
    # VPN Servers
    VPN_SERVERS: List[Dict] = json.loads(os.getenv("VPN_SERVERS", "[]"))
    
    # Payment
    DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "USDT")
    DEFAULT_NETWORK: str = os.getenv("DEFAULT_NETWORK", "TRC20")
    
    # Bot Settings
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
    SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "")

    # VPS Settings (для автоматического добавления пользователей через SSH - устарело)
    VPS_HOST: str = os.getenv("VPS_HOST", "148.253.213.153")
    VPS_SSH_PORT: int = int(os.getenv("VPS_SSH_PORT", "22"))
    VPS_USERNAME: str = os.getenv("VPS_USERNAME", "root")
    VPS_PASSWORD: str = os.getenv("VPS_PASSWORD", "")
    VPS_SSH_KEY_PATH: str = os.getenv("VPS_SSH_KEY_PATH", "")
    
    # 3x-ui API Settings (для работы через API)
    X3UI_API_URL: str = os.getenv("X3UI_API_URL", "http://148.253.213.153:2053")
    X3UI_USERNAME: str = os.getenv("X3UI_USERNAME", "admin")
    X3UI_PASSWORD: str = os.getenv("X3UI_PASSWORD", "admin")
    X3UI_INBOUND_ID: int = int(os.getenv("X3UI_INBOUND_ID", "1"))  # ID inbound в 3x-ui
    USE_X3UI_API: bool = os.getenv("USE_X3UI_API", "true").lower() == "true"  # Использовать 3x-ui API вместо SSH

settings = Settings()