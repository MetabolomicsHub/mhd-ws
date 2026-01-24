import os
from logging.config import fileConfig
from pathlib import Path

import yaml
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import DeclarativeBase

from mhd_ws.run.config_renderer import render_config_secrets
from mhd_ws.run.rest_api.mhd.containers import MHD_CONFIG_FILE, MHD_CONFIG_SECRETS_FILE


class Base(DeclarativeBase):
    @classmethod
    def get_field_alias(cls, name: str) -> str:
        alias_exceptions = cls.get_field_alias_exceptions()
        if name in alias_exceptions:
            return alias_exceptions[name]
        return name

    @classmethod
    def get_field_alias_exceptions(cls):
        return {}


def get_db_url(config_file, secrets_file):
    with Path(config_file).open("r") as f:
        config = yaml.safe_load(f)

    if secrets_file and Path(secrets_file).exists():
        with Path(secrets_file).open("r") as f:
            secrets = yaml.safe_load(f)
        config = render_config_secrets(config, secrets)

    db_config = (
        config.get("gateways", {})
        .get("database", {})
        .get("postgresql", {})
        .get("connection", {})
    )

    user = db_config.get("user")
    password = db_config.get("password")
    host = db_config.get("host")
    port = db_config.get("port")
    db_name = db_config.get("database")

    # Force use of psycopg2 for Alembic (sync)
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


db_url = get_db_url(MHD_CONFIG_FILE, MHD_CONFIG_SECRETS_FILE)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)  # type: ignore

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = os.environ.get("DB_URL", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
