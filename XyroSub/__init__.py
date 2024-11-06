import logging
import sys
from pathlib import Path
from typing import Final, List

from XyroSub.helpers.yaml import load_config

# Initialize Logger
logger = logging.getLogger("[XyroSub]")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
logger.setLevel(logging.INFO)
logger.info("XyroSubBot is starting...")

# Do a version check
if sys.version_info[0] < 3 or sys.version_info[1] < 12:
    logger.error(
        "You MUST have a python version of atleast 3.12! Multiple features depend on this. Bot quitting."
    )
    exit(1)

# YAML Loader
bot_config = load_config("config.yml")
telegram_config = bot_config["telegram"]
database_config = bot_config["database"]
misc_config = bot_config["misc"]
pricing_config = bot_config["pricing"]
affiliate_config = bot_config["affiliate"]

# Telegram Constants
API_ID: Final[int] = telegram_config.get("api_id")
API_HASH: Final[str] = telegram_config.get("api_hash")
BOT_TOKEN: Final[str] = telegram_config.get("bot_token")
GROUP_ID: Final[int] = int(telegram_config.get("group_id"))
TOPIC_ID: Final[int] = int(telegram_config.get("topic_id"))
SUDO_USERS: Final[List[int]] = telegram_config.get("sudo_users")
OWNER_ID: Final[int] = telegram_config.get("owner_id")
SUPPORT_BOT: Final[str] = telegram_config.get("support_bot")
ANNOUNCE_CHANNEL: Final[str] = telegram_config.get("announce_channel")
DROP_UPDATES: Final[bool] = telegram_config.get("drop_updates", True)
PREMIUM_CHANNEL: Final[int] = int(telegram_config.get("premium_channel_id"))

# Database Constants
SCHEMA: Final[str] = database_config.get("schema")

# Misc Constants
DISABLED_PLUGINS: Final[List[str]] = misc_config.get("disable", [])

# PRICING
BASIC_PLAN_PRICE: Final[int] = pricing_config.get("basic_plan_price")
STANDARD_PLAN_PRICE: Final[int] = pricing_config.get("standard_plan_price")
PREMIUM_PLAN_PRICE: Final[int] = pricing_config.get("premium_plan_price")
BASIC_PLAN_DAYS: Final[int] = pricing_config.get("basic_plan_days")
STANDARD_PLAN_DAYS: Final[int] = pricing_config.get("standard_plan_days")
PREMIUM_PLAN_DAYS: Final[int] = pricing_config.get("premium_plan_days")

# Affiliate
MINIMUM_COMMISSION_WITHDRAW: Final[int] = affiliate_config.get(
    "minimum_commission_withdraw") or 1000
AFFILIATE_ALLOWED: Final[bool] = affiliate_config.get("affiliate_allowed", False)
WITHDRAWAL_ALLOWED: Final[bool] = affiliate_config.get("withdrawal_allowed", False)

PROJECT_DIR = Path(__file__).parent.parent
sys.path.append(str(PROJECT_DIR))
