"""Serialize invariant-changing writes across workers on either supported database.

The single PostgreSQL transaction advisory lock deliberately preserves SQLite's
coarse writer serialization. It is appropriate for a small sandbox deployment;
replace it with consistently ordered scoped locks before scaling write throughput.
"""
from sqlalchemy import text


def reserve_write(db):
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(735102946)"))
    else:
        raise RuntimeError("CampusShift supports SQLite and PostgreSQL only")
