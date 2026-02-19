"""
Configuracao do Alembic para migrations do Specter.
Usa os modelos SQLAlchemy definidos em specter/modelos/.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from specter.config import config as specter_config
from specter.modelos.base import Base

import specter.modelos  # noqa: F401 — importa todos os modelos

alembic_config = context.config
alembic_config.set_main_option("sqlalchemy.url", specter_config.POSTGRES_URL)

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
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
