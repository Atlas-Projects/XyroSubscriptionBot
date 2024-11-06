import asyncio
import glob
import importlib
from pathlib import Path

from pyrogram.client import Client
from pyrogram.handlers.handler import Handler

from XyroSub import (API_HASH, API_ID, BOT_TOKEN, DISABLED_PLUGINS,
                     DROP_UPDATES, PROJECT_DIR, logger)
from XyroSub.database import start_db
from XyroSub.modules.start import set_all_bot_commands
from XyroSub.modules.subscription import auto_send_invoices

app = Client("XyroSubBot",
             workdir=Path.cwd(),
             test_mode=True,
             api_id=API_ID,
             api_hash=API_HASH,
             bot_token=BOT_TOKEN,
             skip_updates=DROP_UPDATES)


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_db())

    plugins_glob = str(PROJECT_DIR / "XyroSub" / "modules" / "*.py")
    all_plugins = sorted([Path(p) for p in glob.glob(plugins_glob)],
                         key=lambda p: p.stem)
    enabled_plugins = [
        plugin for plugin in all_plugins
        if plugin.is_file() and plugin.stem not in DISABLED_PLUGINS
    ]

    for plugin_path in enabled_plugins:
        plugin = importlib.import_module(
            f"XyroSub.modules.{plugin_path.stem}")
        for name in vars(plugin).keys():
            try:
                var = getattr(plugin, name)  #pyright: ignore[reportAny]
                for handler, group in var.handlers:  #pyright: ignore[reportAny]
                    if isinstance(handler, Handler) and isinstance(group, int):
                        _ = app.add_handler(handler, group)
                        logger.info(
                            f"[Modules] [LOAD] {type(handler).__name__}('{name}') in group {group} from '{plugin.__name__}'"
                        )
            except Exception:
                pass

    loop.create_task(set_all_bot_commands(client=app))
    loop.create_task(auto_send_invoices(app))

    logger.info("Starting the Pyrogram Client now...")

    app.run()


if __name__ == "__main__":
    main()
