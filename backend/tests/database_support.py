"""Use real pooled PostgreSQL or a file-backed copy of in-memory SQLite."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from app.core.config import BACKEND_DIR, Settings
from main import create_app


@contextmanager
def concurrency_app(app, settings):
    if app.state.engine.dialect.name == "postgresql":
        yield app
        return
    with TemporaryDirectory(dir=BACKEND_DIR) as directory:
        path = Path(directory) / "concurrent.db"
        source = app.state.engine.raw_connection()
        destination = sqlite3.connect(path)
        try:
            source.driver_connection.backup(destination)
        finally:
            destination.close()
            source.close()
        copied = create_app(Settings("sqlite:///" + str(path), settings.jwt_secret, 30, ()))
        try:
            yield copied
        finally:
            copied.state.engine.dispose()
