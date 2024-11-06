import importlib
import os
import time
from pathlib import Path
from typing import Final

from cachetools import LRUCache
from pyrogram import Client

START_UNIX_TIME: Final[int] = int(time.time())
module_cache = LRUCache(maxsize=100)
BOT_SETTINGS_CACHE = LRUCache(maxsize=10)


def get_start_time() -> int:
    return START_UNIX_TIME


async def load_modules(force_reload=False):
    if force_reload:
        module_cache.clear()

    if "modules" in module_cache:
        return module_cache["modules"]

    module_data = []
    module_dir = os.path.join(str(Path(__file__).parent.parent), "modules")

    for entry in os.scandir(module_dir):
        if entry.is_file() and entry.name.endswith(
                ".py") and not entry.name.startswith(
                    "__") and entry.name not in ["help", "start"]:
            module_name = entry.name[:-3]
            module = importlib.import_module(
                f"XyroSub.modules.{module_name}")
            if hasattr(module, "__module_name__") and hasattr(
                    module, "__help_msg__"):
                module_data.append({
                    "name": module.__module_name__,
                    "help_msg": module.__help_msg__
                })

    module_data = sorted(module_data, key=lambda x: x["name"][0])
    module_cache["modules"] = module_data
    return module_data


async def get_bot_object(client: Client):
    if "bot_info" in BOT_SETTINGS_CACHE:
        return BOT_SETTINGS_CACHE["bot_info"]
    bot_info = await client.get_me()
    BOT_SETTINGS_CACHE["bot_info"] = bot_info
    return bot_info

