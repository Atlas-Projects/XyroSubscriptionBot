import glob
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from XyroSub import DISABLED_PLUGINS, PROJECT_DIR, SCHEMA, logger

BASE = declarative_base()


async def start_db() -> None:
    engine = create_async_engine(SCHEMA)
    logger.info("[ORM] Connecting to database...")
    async_session = async_sessionmaker(bind=engine,
                                       autoflush=True,
                                       expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            logger.info("[ORM] Creating tables inside database now...")
            async with engine.begin() as conn:
                database_plugins_glob = str(PROJECT_DIR / "NeoSupport" /
                                            "database" / "*.py")
                database_plugins = sorted([
                    Path(plugin) for plugin in glob.glob(database_plugins_glob)
                ],
                                          key=lambda p: p.stem)
                enabled_database_plugins = [
                    plugin for plugin in database_plugins
                    if plugin.is_file() and plugin.stem not in DISABLED_PLUGINS
                    and plugin.name != "__init__.py"
                ]

                for plugin_path in enabled_database_plugins:
                    module_path = f"NeoSupport.database.{plugin_path.stem}"
                    logger.info(
                        f"[DATABASE] [LOAD] importing and creating tables from '{module_path}'"
                    )
                    __import__(module_path)

                await conn.run_sync(BASE.metadata.create_all)
            logger.info("[ORM] Connection successful, session started.")
