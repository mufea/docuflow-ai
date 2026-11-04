from __future__ import annotations

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from docuflow.dsn import normalize_database_url

logger = logging.getLogger("docuflow.migrate")

# Stable key so API replicas serialize Alembic upgrades.
ADVISORY_LOCK_KEY = 86420138


def alembic_config() -> Config:
    candidates = [
        Path.cwd() / "alembic.ini",
        Path(__file__).resolve().parents[2] / "alembic.ini",
    ]
    for ini in candidates:
        if ini.is_file():
            config = Config(str(ini))
            config.set_main_option("script_location", str(ini.parent / "alembic"))
            return config
    raise RuntimeError("alembic.ini was not found in the working directory or package root.")


def upgrade_head(database_url: str | None = None) -> None:
    raw = database_url or os.environ.get("DATABASE_URL", "")
    url = normalize_database_url(raw) if raw else ""
    config = alembic_config()
    if url:
        config.set_main_option("sqlalchemy.url", url)
    if url.startswith("postgresql"):
        engine = create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY})
            connection.commit()
            logger.info("alembic_upgrade_locked")
            try:
                command.upgrade(config, "head")
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
                connection.commit()
                logger.info("alembic_upgrade_unlocked")
        engine.dispose()
        return
    command.upgrade(config, "head")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    upgrade_head()


if __name__ == "__main__":
    main()
