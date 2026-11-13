"""Cold-start configuration only. No AWS SDK/network calls and no schema changes.

Secrets Manager references are resolved by CloudFormation into encrypted Lambda
configuration. libpq reads a private temporary passfile, keeping passwords out of
DATABASE_URL and SQLAlchemy connection/error strings. Lambda /tmp is not a DB.
"""
import logging
import os
from pathlib import Path
import tempfile
from sqlalchemy.engine import make_url
from app.core.logging_config import JSONFormatter


def prepare_environment():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    # Mangum's INFO request line includes the raw path rather than our safe
    # route template. Keep its generic errors, suppress identifying path logs.
    logging.getLogger("mangum.http").setLevel(logging.WARNING)
    if os.getenv("APP_ENV") != "production" or os.getenv("DB_POOLING") != "null":
        raise ValueError("Lambda requires production configuration with DB_POOLING=null")
    url = make_url(os.environ["DATABASE_URL"])
    if url.drivername != "postgresql+psycopg" or url.password is not None:
        raise ValueError("Lambda requires a password-free PostgreSQL psycopg URL")
    if url.query.get("sslmode") != "verify-full" or not Path(url.query.get("sslrootcert", "")).is_file():
        raise ValueError("Lambda requires verify-full and the packaged RDS CA bundle")
    password = os.environ.get("DB_PASSWORD", "")
    if not password or any(char in password for char in "\r\n"):
        raise ValueError("Missing or invalid database credential")
    lines = [(url.username, password)]
    if os.environ.get("APP_DB_PASSWORD"):
        lines.append((os.environ["APP_DB_USERNAME"], os.environ["APP_DB_PASSWORD"]))
    if any(not value or any(char in str(value) for char in "\r\n")
           for value in (url.host, url.database, *[v for pair in lines for v in pair])):
        raise ValueError("Invalid passfile configuration")
    directory = Path(tempfile.mkdtemp(prefix="campusshift-"))
    directory.chmod(0o700)
    path = directory / "pgpass"
    def escape(value):
        return str(value).replace("\\", "\\\\").replace(":", "\\:")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        for username, secret in lines:
            stream.write(":".join(escape(value) for value in (url.host, url.port or 5432, url.database, username, secret)) + "\n")
    os.environ["PGPASSFILE"] = str(path)

