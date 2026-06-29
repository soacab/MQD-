from logging.config import fileConfig

from alembic import context

from app.core.database import SCHEMA_SQL


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.execute(SCHEMA_SQL)


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection")
    if connectable is None:
        raise RuntimeError("Run migrations with an injected SQLAlchemy connection for this MVP.")
    with connectable.begin() as connection:
        context.configure(connection=connection)
        context.execute(SCHEMA_SQL)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
