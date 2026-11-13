"""IAM-only deployment jobs. This function has no API route, URL or public grant."""
from datetime import timedelta
from functools import lru_cache
import logging
import os
from pathlib import Path
import re
from time import monotonic

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from psycopg import ClientCursor, sql

from app.core.config import Settings
from app.core.attendance_time import now_utc, zone
from app.db.session import create_session_factory

logger = logging.getLogger(__name__)
MIGRATION_LOCK = 735102947
HEAD = "9e57ab896061"


@lru_cache(maxsize=1)
def initialize():
    from app.core.lambda_runtime import prepare_environment
    prepare_environment()


def grant_app_access(engine, username, password):
    """Fresh application login gets DML only; existing passwords are preserved.

    ClientCursor safely quotes DDL values. Neither the SQL nor the password is
    passed through a statement logger or returned. Do not enable SQL logging.
    """
    if not re.fullmatch(r"[a-z][a-z0-9]{2,40}", username) or not password:
        raise ValueError("Invalid application role configuration")
    with engine.begin() as connection:
        with ClientCursor(connection.connection.driver_connection) as cursor:
            cursor.execute("SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=%s", (username,))
            role = cursor.fetchone()
            if role is None:
                cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %s").format(sql.Identifier(username)), (password,))
            elif role != (True, False, False, False):
                raise ValueError("Existing app role has unexpected administrative attributes")
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            for statement in (
                "GRANT USAGE ON SCHEMA public TO {}",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}",
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}",
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}",
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}",
            ):
                cursor.execute(sql.SQL(statement).format(sql.Identifier(username)))
            # Readiness may read the revision; application requests never edit it.
            cursor.execute(sql.SQL("REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM {}").format(sql.Identifier(username)))
    return role is None


def run_job(event, settings=None):
    if not isinstance(event, dict) or set(event) - {"action", "demo_password"}:
        raise ValueError("Only explicit private job actions are accepted")
    action = event.get("action")
    if action not in {"migrate", "check", "seed"}:
        raise ValueError("Unknown private job action")
    settings = settings or Settings.from_env()
    if not settings.database_url.startswith("postgresql+psycopg://") or settings.db_pooling != "null":
        raise ValueError("Private jobs require PostgreSQL and null pooling")
    engine, factory = create_session_factory(settings.database_url, **settings.database_options)
    try:
        # Session lock serializes private deployment jobs without holding a DB
        # transaction open across Alembic's independent migration connections.
        with engine.connect() as lock:
            if not lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK}).scalar():
                raise RuntimeError("Another private deployment job is already running")
            lock.commit()
            try:
                config = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
                if action == "migrate":
                    command.upgrade(config, "head")
                    command.check(config)
                    created = grant_app_access(engine, os.environ["APP_DB_USERNAME"], os.environ["APP_DB_PASSWORD"])
                    return {"action": action, "schema_revision": HEAD, "app_role_created": created}
                with engine.connect() as connection:
                    if connection.execute(text("SELECT version_num FROM alembic_version")).scalar() != HEAD:
                        raise RuntimeError("Run the migration job first")
                if action == "check":
                    command.check(config)
                    return {"action": action, "schema_revision": HEAD}
                password = event.get("demo_password", "")
                from app.schemas import Register
                from app.seed_cloud_demo import populate
                Register(full_name="Synthetic Demo", email="scheduling.supervisor@example.com", department_id=1, password=password)
                today = now_utc().astimezone(zone("America/Chicago")).date()
                monday = today - timedelta(days=today.weekday() + 7)
                with factory() as db:
                    run_id, added = populate(db, password, monday)
                return {"action": action, "run_id": run_id, "attendance_records_added": added}
            finally:
                lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
                lock.commit()
    finally:
        engine.dispose()


def handler(event, context):
    started = monotonic()
    try:
        initialize()
        result = run_job(event)
        logger.info("Private deployment job succeeded action=%s", result["action"])
        return {"ok": True, **result, "duration_ms": int((monotonic() - started) * 1000)}
    except Exception as error:
        # Validation errors can include input/password values. Never serialize
        # event, str(error), a traceback, or environment configuration here.
        logger.error("Private deployment job failed type=%s", type(error).__name__)
        return {"ok": False, "error": "Private deployment job failed; inspect configuration and safe logs", "error_type": type(error).__name__}
