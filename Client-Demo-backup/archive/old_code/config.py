import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from the same directory as this file, or fall back to home
env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv(os.path.expanduser('~/.env'))  # legacy fallback

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

# Alpaca
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
# Coinbase
COINBASE_API_KEY = os.getenv("COINBASE_API_KEY")
COINBASE_API_SECRET = os.getenv("COINBASE_API_SECRET")
COINBASE_PASSPHRASE = os.getenv("COINBASE_PASSPHRASE", "")

# Web search
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")


AI_NAME = os.getenv("AI_NAME", "Jeeves")

# LLM
LLM_URL = os.getenv("LLM_URL", "http://localhost:8080/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "llama")
LLM_CTX_SIZE = int(os.getenv("LLM_CTX_SIZE", "4096"))

# File paths – expand ~ to user home
PERSONA_FILE = os.path.expanduser(os.getenv("PERSONA_FILE", "~/jeeves_persona.txt"))
MIRROR_LOG = os.path.expanduser(os.getenv("MIRROR_LOG", "~/mirror.log"))
LAKE_INDEX_PATH = os.path.expanduser(os.getenv("LAKE_INDEX_PATH", "/mnt/lake/index"))
CRYPTO_STRATEGY_FILE = os.path.expanduser(os.getenv("CRYPTO_STRATEGY_FILE", "~/crypto_sim_strategy.txt"))
CRYPTO_MIRROR_LOG = os.path.expanduser(os.getenv("CRYPTO_MIRROR_LOG", "~/crypto_sim_mirror.log"))
TRADING_STRATEGY_FILE = os.path.expanduser(os.getenv("TRADING_STRATEGY_FILE", "~/trading_strategy.txt"))
TRADING_MIRROR_LOG = os.path.expanduser(os.getenv("TRADING_MIRROR_LOG", "~/trading_mirror.log"))

USER_NAME = os.getenv("USER_NAME", "")
