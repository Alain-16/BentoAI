import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importing this pulls in all five model files, which is what makes the twelve
# tables register themselves. Without it Alembic sees an empty catalogue and
# happily writes a migration that drops everything.
import bentoai.models  # noqa: F401
from bentoai.config import get_settings
from bentoai.shared.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Take the address from our settings rather than alembic.ini, so there is one
# place it is written down.
#
# The .replace("%", "%%") is not decoration. This config file format treats % as
# a special character, so a password containing one — which generated passwords
# often do — makes Alembic crash with an error that says nothing about passwords.
# Doubling them up escapes them.
config.set_main_option("sqlalchemy.url", get_settings().db.url_str.replace("%", "%%"))


# What the database *should* look like. Alembic compares this against what is
# actually there and writes the difference.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Print the SQL instead of running it.

    Used with `alembic upgrade head --sql` when a DBA wants to review or ru
    statements by hand rather than letting a tool touch production.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run the migrations on an already-open connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Notice when a column's type changes, e.g. String(100) to String(2
        # Off by default, which means silent misses.
        compare_type=True,
        # Notice when a column's default changes.
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async connection and hand it to the migration runner."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool means do not keep connections around. A migration is a o
        # command that exits straight afterwards, so pooling would only del
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Alembic's internals are synchronous. run_sync bridges the two wor
        # running the sync migration code on top of the async connection.
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()