from alembic import context

from app.core.config import Settings
from app.db.session import Base, create_session_factory
import app.models  # Register the complete model metadata.

target_metadata = Base.metadata
settings = Settings.from_env()

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=settings.database_url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()
else:
    engine, _ = create_session_factory(settings.database_url, **settings.database_options)
    try:
        with engine.connect() as connection:
            sqlite = connection.dialect.name == "sqlite"
            if sqlite:
                # Batch migrations rebuild referenced tables. Disable enforcement
                # only on this migration connection, then verify every FK below.
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.commit()
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=sqlite)
            with context.begin_transaction():
                context.run_migrations()
            if sqlite:
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("Migration failed foreign-key consistency check")
                connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    finally:
        engine.dispose()
