"""Run existing business contracts through real HTTP API v2/Mangum events.

No AWS calls. PostgreSQL variants use the disposable database harness. These
events do not emulate AWS latency, VPC networking, throttling or Aurora resume.
"""
import asyncio
import base64
from dataclasses import replace
import os
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
import psycopg
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.db.session import connect_with_retry, create_session_factory
from lambda_handler import make_handler
import lambda_jobs
import test_phase2
import test_scheduling
import test_workflows
import test_attendance


class EventClient:
    def __init__(self, app):
        self.adapter = make_handler(app)

    def request(self, method, path, *, headers=None, json=None, params=None, **kwargs):
        url = urlsplit(path)
        query = urlencode(params or {}, doseq=True) or url.query
        event = {"version": "2.0", "routeKey": "$default", "rawPath": url.path,
                 "rawQueryString": query, "headers": {"host": "test.execute-api.us-east-2.amazonaws.com",
                    "content-type": "application/json", **{key.lower(): value for key, value in (headers or {}).items()}},
                 "requestContext": {"stage": "$default", "requestId": "local-contract-test",
                    "http": {"method": method.upper(), "path": url.path, "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}},
                 "body": __import__("json").dumps(json) if json is not None else "", "isBase64Encoded": False}
        # Mangum is synchronous and Lambda supplies a reusable thread event loop.
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        result = self.adapter(event, Mock())
        content = base64.b64decode(result["body"]) if result.get("isBase64Encoded") else result["body"].encode()
        return httpx.Response(result["statusCode"], headers=result.get("headers", {}), content=content)

    def __getattr__(self, method):
        if method in {"get", "post", "patch", "put", "delete", "options"}:
            return lambda path, **kwargs: self.request(method, path, **kwargs)
        raise AttributeError(method)


class LambdaEvents:
    def setUp(self):
        super().setUp()
        if self.settings.database_url.startswith("postgresql"):
            from main import create_app
            self.app.state.engine.dispose()
            self.settings = replace(self.settings, db_pooling="null")
            self.app = create_app(self.settings)
            self.addCleanup(self.app.state.engine.dispose)
            self.assertIsInstance(self.app.state.engine.pool, NullPool)
        self.client = EventClient(self.app)


class LambdaAuthTests(LambdaEvents, test_phase2.Phase2Tests):
    pass


class LambdaSchedulingTests(LambdaEvents, test_scheduling.SchedulingApiTests):
    def test_failure_rolls_back_entire_draft(self):
        from sqlalchemy import func, select
        from app.models import ScheduleRun, AssignedShift
        self.scenario()
        with patch("app.services.scheduling.AssignedShift", side_effect=RuntimeError("simulated persistence failure")), patch("logging.Logger.exception"):
            response = self.request("POST", "/supervisor/schedules", user_id=4, json={"week_start": "2026-10-19"})
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("simulated", response.text)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ScheduleRun)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AssignedShift)), 0)


class LambdaWorkflowTests(LambdaEvents, test_workflows.WorkflowTests):
    # Original tests assert TestClient re-raises injected exceptions. HTTP
    # adapters instead return 500; transport-specific failure is covered above.
    test_partial_unique_index_and_publish_failure_rollback = unittest.skip("Exception re-raise contract covered in original ASGI test")(test_workflows.WorkflowTests.test_partial_unique_index_and_publish_failure_rollback)
    test_remove_refill_capacity_and_atomic_failure = unittest.skip("Exception re-raise contract covered in original ASGI test")(test_workflows.WorkflowTests.test_remove_refill_capacity_and_atomic_failure)


class LambdaAttendanceTests(LambdaEvents, test_attendance.AttendanceTests):
    test_failure_rolls_back_clock_in_and_correction = unittest.skip("Exception re-raise contract covered in original ASGI test")(test_attendance.AttendanceTests.test_failure_rolls_back_clock_in_and_correction)


class ConnectionRetryTests(unittest.TestCase):
    def test_retries_connection_only_and_never_retries_bad_credentials(self):
        success = object()
        connect = Mock(side_effect=[psycopg.OperationalError("connection timed out"), success])
        with patch("app.db.session.time.sleep") as sleep:
            self.assertIs(connect_with_retry(connect, [], {}, psycopg.OperationalError, 2, 1), success)
            sleep.assert_called_once_with(1)
        for message in ("password authentication failed", "certificate verify failed", "no password supplied"):
            connect = Mock(side_effect=psycopg.OperationalError(message))
            with self.assertRaises(psycopg.OperationalError):
                connect_with_retry(connect, [], {}, psycopg.OperationalError, 3, 0)
            self.assertEqual(connect.call_count, 1)
        connect = Mock(side_effect=psycopg.OperationalError("connection timed out"))
        with self.assertRaises(psycopg.OperationalError):
            connect_with_retry(connect, [], {}, psycopg.OperationalError, 2, 0)
        self.assertEqual(connect.call_count, 2)

    def test_private_job_rejects_http_and_does_not_log_passwords(self):
        for event in ({"version": "2.0", "action": "migrate"}, {"action": "delete"}):
            with self.assertRaises(ValueError):
                lambda_jobs.run_job(event)
        with patch.object(lambda_jobs, "initialize"), patch.object(lambda_jobs, "run_job", side_effect=ValueError("PASSWORD-MUST-NOT-LOG")), self.assertLogs("lambda_jobs", level="ERROR") as logs:
            response = lambda_jobs.handler({"action": "seed", "demo_password": "PASSWORD-MUST-NOT-LOG"}, None)
        self.assertFalse(response["ok"])
        self.assertNotIn("PASSWORD-MUST-NOT-LOG", str(logs.output) + str(response))


@unittest.skipUnless(os.getenv("TEST_POSTGRESQL_URL"), "Disposable PostgreSQL job integration")
class PrivateJobTests(unittest.TestCase):
    def test_migrate_seed_dml_role_and_null_pool_close(self):
        admin_url = make_url(os.environ["TEST_POSTGRESQL_URL"])
        database = "lambda_" + uuid4().hex[:12]
        role = "app" + uuid4().hex[:12]
        password = "test-only-" + uuid4().hex
        admin, _ = create_session_factory(admin_url.render_as_string(hide_password=False), pooling="null")
        url = admin_url.set(database=database).render_as_string(hide_password=False)
        engine = None
        try:
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
                db.execute(text(f'CREATE DATABASE "{database}"'))
            env = {"DATABASE_URL": url, "APP_ENV": "test", "DB_POOLING": "null", "APP_DB_USERNAME": role, "APP_DB_PASSWORD": password}
            with patch.dict(os.environ, env):
                self.assertTrue(lambda_jobs.run_job({"action": "migrate"})["app_role_created"])
                self.assertFalse(lambda_jobs.run_job({"action": "migrate"})["app_role_created"])
                self.assertEqual(lambda_jobs.run_job({"action": "check"})["schema_revision"], lambda_jobs.HEAD)
                self.assertEqual(lambda_jobs.run_job({"action": "seed", "demo_password": password})["attendance_records_added"], 2)
                self.assertEqual(lambda_jobs.run_job({"action": "seed", "demo_password": password})["attendance_records_added"], 0)
            app_url = make_url(url).set(username=role, password=password).render_as_string(hide_password=False)
            engine, _ = create_session_factory(app_url, pooling="null", connect_attempts=2,
                                               statement_timeout_ms=5000, lock_timeout_ms=2000)
            self.assertIsInstance(engine.pool, NullPool)
            with engine.connect() as db:
                self.assertEqual(db.execute(text("SHOW statement_timeout")).scalar(), "5s")
                self.assertEqual(db.execute(text("SHOW lock_timeout")).scalar(), "2s")
                self.assertGreater(db.execute(text("SELECT count(*) FROM users")).scalar(), 0)
                with self.assertRaises(Exception):
                    db.execute(text("CREATE TABLE forbidden (id integer)"))
            with admin.connect() as db:
                self.assertEqual(db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE usename=:name"), {"name": role}).scalar(), 0)
        finally:
            if engine is not None:
                engine.dispose()
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
                db.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
                db.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
            admin.dispose()
