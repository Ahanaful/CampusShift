"""Production settings, readiness, real PostgreSQL migrations and concurrency."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from app.core.config import BACKEND_DIR, Settings
from app.core.logging_config import JSONFormatter
from app.db.session import create_session_factory
from app.models import AttendanceRecord, ScheduleRun
from app.seed_cloud_demo import populate
from main import create_app
import test_phase2


class ProductionTests(unittest.TestCase):
    def test_production_fails_closed_for_sqlite_secret_and_http_cors(self):
        valid = {"APP_ENV": "production", "DATABASE_URL": "postgresql://user@host/campusshift", "JWT_SECRET": "x" * 48, "CORS_ORIGINS": ""}
        with patch.dict(os.environ, valid), patch("app.core.config.load_dotenv"):
            self.assertTrue(Settings.from_env().database_url.startswith("postgresql+psycopg://"))
            for changes in ({"DATABASE_URL": "sqlite://"}, {"JWT_SECRET": "short"}, {"CORS_ORIGINS": "http://example.com"}):
                with patch.dict(os.environ, changes), self.assertRaises(ValueError):
                    Settings.from_env()

    def test_readiness_requires_migrations_and_production_hides_docs(self):
        with TemporaryDirectory() as directory:
            url = "sqlite:///" + str(Path(directory) / "test.db")
            app = create_app(Settings(url, "x" * 48, 30, (), environment="production"))
            try:
                with TestClient(app) as client:
                    self.assertEqual(client.get("/api/health").status_code, 200)
                    self.assertEqual(client.get("/api/ready").status_code, 503)
                    self.assertEqual(client.get("/docs").status_code, 404)
                    config = Config(str(BACKEND_DIR / "alembic.ini"))
                    with patch.dict(os.environ, {"DATABASE_URL": url, "APP_ENV": "test"}):
                        command.upgrade(config, "head")
                    self.assertEqual(client.get("/api/ready").json(), {"status": "ready"})
            finally:
                app.state.engine.dispose()

    def test_structured_logging_omits_exception_payload(self):
        try:
            raise RuntimeError("private-connection-string")
        except RuntimeError:
            import sys
            record = logging.LogRecord("test", logging.ERROR, "", 0, "Operation failed", (), sys.exc_info())
        data = JSONFormatter().format(record)
        self.assertNotIn("private-connection-string", data)
        self.assertEqual(json.loads(data)["exception_type"], "RuntimeError")


@unittest.skipUnless(os.getenv("TEST_POSTGRESQL_URL"), "Run scripts/test_postgresql.py for disposable PostgreSQL verification")
class PostgreSQLMigrationTests(unittest.TestCase):
    def test_all_migrations_round_trip_demo_persistence_and_model_check(self):
        raw_url = os.environ["TEST_POSTGRESQL_URL"]
        admin, _ = create_session_factory(raw_url)
        schema = "test_migration_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(raw_url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        engine, factory = create_session_factory(url)
        try:
            with patch.dict(os.environ, {"DATABASE_URL": url, "APP_ENV": "test"}):
                command.upgrade(config, "head")
                command.check(config)
                command.downgrade(config, "base")
                command.upgrade(config, "head")
                monday = date.today() - timedelta(days=date.today().weekday() + 14)
                with factory() as db:
                    run_id, count = populate(db, test_phase2.PASSWORD, monday)
                    self.assertEqual(count, 2)
                with factory() as db:
                    self.assertEqual(db.get(ScheduleRun, run_id).status, "published")
                    self.assertEqual(len(list(db.scalars(select(AttendanceRecord)))), 2)
                engine.dispose()
                engine, factory = create_session_factory(url)
                with factory() as db:
                    self.assertIsNotNone(db.get(ScheduleRun, run_id))
                    again, count = populate(db, test_phase2.PASSWORD, monday)
                    self.assertEqual(again, run_id)
                    self.assertEqual(count, 0)
                indexes = {index["name"]: index for index in inspect(engine).get_indexes("attendance_records")}
                self.assertTrue(indexes["uq_active_attendance_student"]["unique"])
                self.assertIn("postgresql_where", indexes["uq_active_attendance_student"]["dialect_options"])
                command.check(config)
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


@unittest.skipUnless(os.getenv("TEST_POSTGRESQL_URL"), "PostgreSQL concurrency test")
class PostgreSQLConcurrencyTests(unittest.TestCase):
    setUpClass = classmethod(test_phase2.Phase2Tests.setUpClass.__func__)
    setUp = test_phase2.Phase2Tests.setUp
    headers = test_phase2.Phase2Tests.headers

    def test_concurrent_overlapping_availability_only_one_succeeds(self):
        body = {"day_of_week": 0, "start_time": "09:00", "end_time": "12:00"}
        def write(_):
            with TestClient(self.app) as client:
                return client.post("/api/students/me/availability", headers=self.headers(), json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(write, range(2))), [201, 409])
