from sqlalchemy import create_engine, event
import logging
import time
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool, NullPool

logger = logging.getLogger(__name__)


def connect_with_retry(connect, args, params, operational_error, attempts, backoff):
    """Retry only initial connection establishment, never a statement/transaction.

    Authentication/configuration failures fail immediately. A no-SQLSTATE network
    failure or Aurora 'cannot connect now' can be transient during resume.
    """
    for attempt in range(attempts):
        try:
            return connect(*args, **params)
        except operational_error as error:
            state = getattr(error, "sqlstate", None)
            message = str(error).lower()
            permanent = any(value in message for value in (
                "password authentication", "no password supplied", "certificate",
                "pg_hba.conf", "invalid connection option", "invalid sslmode"))
            transient = state is None or state.startswith("08") or state in {"57P03", "53300"}
            if permanent or not transient or attempt + 1 == attempts:
                raise
            # Error text can contain connection details; log only the attempt.
            logger.info("Database connection retry attempt=%s", attempt + 2)
            time.sleep(backoff)


class Base(DeclarativeBase):
    pass


def create_session_factory(url: str, *, pooling="queue", connect_timeout=5,
                           connect_attempts=1, connect_backoff=1,
                           statement_timeout_ms=0, lock_timeout_ms=0):
    kwargs = {"pool_pre_ping": True, "hide_parameters": True}
    if pooling not in {"queue", "null"}:
        raise ValueError("Unsupported database pooling")
    if pooling == "null":
        kwargs.update(poolclass=NullPool, pool_pre_ping=False)
    if url.startswith("postgresql"):
        kwargs["connect_args"] = {"connect_timeout": connect_timeout}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "postgresql":
        @event.listens_for(engine, "do_connect")
        def connect_postgresql(dialect, connection_record, args, params):
            return connect_with_retry(dialect.connect, args, params,
                dialect.loaded_dbapi.OperationalError, connect_attempts, connect_backoff)

        @event.listens_for(engine, "connect")
        def set_utc(connection, _):
            # Set session state outside a transaction so a rollback cannot undo it.
            previous = connection.autocommit
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute(f"SET statement_timeout = {int(statement_timeout_ms)}")
                cursor.execute(f"SET lock_timeout = {int(lock_timeout_ms)}")
            connection.autocommit = previous
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
