from logging.config import fileConfig

from alembic import context
from alembic.util import CommandError
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def configured_url():
    try:
        url = settings.get_database_url()
    except ValueError as exc:
        raise CommandError(str(exc)) from None
    if url is None:
        raise CommandError(
            "PostgreSQL is not configured. Set DATABASE_URL or POSTGRES_SERVER, "
            "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB in the environment or services/api/.env."
        )
    return url


def run_migrations_offline() -> None:
    url = configured_url()
    context.configure(
        url=url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(configured_url(), poolclass=pool.NullPool)
    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
