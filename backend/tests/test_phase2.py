"""Authorization, data integrity and CRUD contracts against isolated SQLite."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import jwt
from sqlalchemy import inspect, select

from app.core.config import BACKEND_DIR, Settings
from app.core.security import hasher
from app.db.session import Base, create_session_factory
from app.models import Department, User
from main import create_app

PASSWORD = "test-only-passphrase-123"


class Phase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hasher.hash(PASSWORD)

    def setUp(self):
        self.settings = Settings("sqlite://", "test-only-secret-with-at-least-32-bytes", 30, ("http://localhost:5173",))
        self.app = create_app(self.settings)
        Base.metadata.create_all(self.app.state.engine)
        self.client = TestClient(self.app)
        self.addCleanup(self.app.state.engine.dispose)
        self.addCleanup(self.client.close)
        with self.app.state.session_factory() as db:
            db.add_all([Department(id=1, name="Library", description="Library team"),
                        Department(id=2, name="IT", description="IT team")])
            db.flush()
            for user_id, role, department in [(1, "student", 1), (2, "student", 1), (3, "student", 2),
                                               (4, "supervisor", 1), (5, "supervisor", 2)]:
                db.add(User(id=user_id, full_name=f"User {user_id}", email=f"user{user_id}@example.com",
                            role=role, department_id=department, password_hash=self.password_hash, max_weekly_hours=20))
            db.commit()

    def headers(self, user_id=1):
        now = datetime.now(timezone.utc)
        token = jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=30),
                            "iss": "campusshift", "aud": "campusshift-web"}, self.settings.jwt_secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def request(self, method, path, user_id=1, **kwargs):
        return self.client.request(method, "/api" + path, headers=self.headers(user_id), **kwargs)

    def window(self, kind="classes", **changes):
        data = {"day_of_week": 0, "start_time": "09:00", "end_time": "10:00"}
        if kind == "classes":
            data["course_name"] = "Cloud Computing"
        return {**data, **changes}

    def test_registration_login_and_current_user(self):
        payload = {"full_name": "New Student", "email": "New@Example.com", "password": PASSWORD, "department_id": 1}
        result = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["role"], "student")
        self.assertEqual(result.json()["email"], "new@example.com")
        self.assertNotIn("password_hash", result.json())
        with self.app.state.session_factory() as db:
            user = db.scalar(select(User).where(User.email == "new@example.com"))
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertNotEqual(user.password_hash, PASSWORD)
        login = self.client.post("/api/auth/login", json={"email": "NEW@example.com", "password": PASSWORD})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["expires_in"], 1800)
        self.assertEqual(login.headers["cache-control"], "no-store")
        me = self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["full_name"], "New Student")
        self.assertNotIn("password_hash", me.json())
        self.assertEqual(self.client.post("/api/auth/register", json=payload).status_code, 409)

    def test_registration_rejects_privilege_escalation_and_invalid_data(self):
        base = {"full_name": "Student", "email": "new@example.com", "password": PASSWORD, "department_id": 1}
        for changes in [{"role": "supervisor"}, {"password": "short"}, {"department_id": 999},
                        {"email": "invalid"}, {"full_name": "   "}, {"max_weekly_hours": 40}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/api/auth/register", json={**base, **changes}).status_code, 422)

    def test_incorrect_password_and_unknown_account(self):
        for email in ["user1@example.com", "missing@example.com"]:
            result = self.client.post("/api/auth/login", json={"email": email, "password": "incorrect"})
            self.assertEqual(result.status_code, 401)
            self.assertEqual(result.json()["detail"], "Email or password is incorrect.")

    def test_missing_invalid_expired_and_deleted_user_tokens(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        expired = jwt.encode({"sub": "1", "iat": 1, "exp": 2, "iss": "campusshift", "aud": "campusshift-web"}, self.settings.jwt_secret, algorithm="HS256")
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + expired}).status_code, 401)
        self.assertEqual(self.request("GET", "/auth/me", user_id=999).status_code, 401)
        for path in ["/students/me/classes", "/students/me/availability", "/supervisor/employees"]:
            self.assertEqual(self.client.get("/api" + path).status_code, 401)

    def test_missing_secret_fails_closed(self):
        app = create_app(Settings("sqlite://", "", 30, ()))
        self.addCleanup(app.state.engine.dispose)
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").status_code, 200)
            self.assertEqual(client.post("/api/auth/login", json={"email": "user1@example.com", "password": PASSWORD}).status_code, 503)

    def test_role_permissions(self):
        for method, path, body in [("GET", "/supervisor/employees", None), ("GET", "/supervisor/department", None),
                                   ("PATCH", "/supervisor/employees/2", {"max_weekly_hours": 10})]:
            self.assertEqual(self.request(method, path, json=body).status_code, 403)
        for path in ["classes", "availability"]:
            self.assertEqual(self.request("GET", "/students/me/" + path, user_id=4).status_code, 403)
            self.assertEqual(self.request("POST", "/students/me/" + path, user_id=4, json=self.window(path)).status_code, 403)

    def test_department_directory_and_isolation(self):
        directory = self.request("GET", "/supervisor/employees", user_id=4)
        self.assertEqual({user["id"] for user in directory.json()}, {1, 2})
        self.assertNotIn("password_hash", directory.text)
        self.assertEqual(self.request("GET", "/supervisor/department", user_id=4).json()["id"], 1)
        for suffix in ["", "/classes", "/availability", "/conflicts"]:
            self.assertEqual(self.request("GET", "/supervisor/employees/1" + suffix, user_id=4).status_code, 200)
            self.assertEqual(self.request("GET", "/supervisor/employees/3" + suffix, user_id=4).status_code, 404)
        self.assertEqual(self.request("PATCH", "/supervisor/employees/3", user_id=4, json={"max_weekly_hours": 10}).status_code, 404)
        self.assertEqual(self.request("PATCH", "/supervisor/employees/1", user_id=4, json={"max_weekly_hours": 15}).json()["max_weekly_hours"], 15)

    def test_profile_update_and_protected_fields(self):
        result = self.request("PATCH", "/students/me", json={"full_name": "Updated Name", "max_weekly_hours": 12})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["max_weekly_hours"], 12)
        for changes in [{"role": "supervisor"}, {"department_id": 2}, {"max_weekly_hours": 41}, {"full_name": " "}]:
            self.assertEqual(self.request("PATCH", "/students/me", json={"full_name": "Student", "max_weekly_hours": 12, **changes}).status_code, 422)

    def test_class_crud(self):
        self.check_crud("classes")

    def test_availability_crud(self):
        self.check_crud("availability")

    def check_crud(self, kind):
        path = "/students/me/" + kind
        result = self.request("POST", path, json=self.window(kind))
        self.assertEqual(result.status_code, 201, result.text)
        entry_id = result.json()["id"]
        self.assertEqual(len(self.request("GET", path).json()), 1)
        changed = self.window(kind, start_time="10:00", end_time="11:00")
        self.assertEqual(self.request("PUT", f"{path}/{entry_id}", json=changed).status_code, 200)
        self.assertEqual(self.request("GET", path).json()[0]["start_time"], "10:00:00")
        self.assertEqual(self.request("DELETE", f"{path}/{entry_id}").status_code, 204)
        self.assertEqual(self.request("GET", path).json(), [])
        self.assertEqual(self.request("DELETE", f"{path}/{entry_id}").status_code, 404)

    def test_ownership_restrictions_for_both_types(self):
        for kind in ["classes", "availability"]:
            path = "/students/me/" + kind
            entry_id = self.request("POST", path, json=self.window(kind)).json()["id"]
            for other in [2, 3]:
                self.assertEqual(self.request("GET", path, user_id=other).json(), [])
                self.assertEqual(self.request("PUT", f"{path}/{entry_id}", user_id=other, json=self.window(kind)).status_code, 404)
                self.assertEqual(self.request("DELETE", f"{path}/{entry_id}", user_id=other).status_code, 404)
            self.assertEqual(self.request("POST", path, json={**self.window(kind), "student_id": 2}).status_code, 422)

    def test_overlaps_and_adjacent_windows(self):
        for kind in ["classes", "availability"]:
            path = "/students/me/" + kind
            first = self.request("POST", path, json=self.window(kind)).json()["id"]
            for start, end in [("09:00", "10:00"), ("08:00", "11:00"), ("09:15", "09:30"), ("08:30", "09:30")]:
                self.assertEqual(self.request("POST", path, json=self.window(kind, start_time=start, end_time=end)).status_code, 409)
            adjacent = self.request("POST", path, json=self.window(kind, start_time="10:00", end_time="11:00"))
            self.assertEqual(adjacent.status_code, 201)
            self.assertEqual(self.request("PUT", f"{path}/{adjacent.json()['id']}", json=self.window(kind)).status_code, 409)
            self.assertEqual(self.request("PUT", f"{path}/{first}", json=self.window(kind)).status_code, 200)
            self.assertEqual(self.request("POST", path, json=self.window(kind, day_of_week=1)).status_code, 201)

    def test_invalid_ranges_and_days(self):
        for kind in ["classes", "availability"]:
            for changes in [{"start_time": "10:00", "end_time": "09:00"}, {"end_time": "09:00"},
                            {"day_of_week": 7}, {"day_of_week": -1}, {"start_time": "invalid"},
                            {"start_time": "09:00:30"}, {"start_time": "09:00:00+01:00"}]:
                self.assertEqual(self.request("POST", "/students/me/" + kind, json=self.window(kind, **changes)).status_code, 422)

    def test_cross_type_conflict_report_preserves_entries(self):
        class_entry = self.request("POST", "/students/me/classes", json=self.window()).json()
        availability = self.request("POST", "/students/me/availability", json=self.window("availability", start_time="09:30", end_time="11:00")).json()
        result = self.request("GET", "/students/me/conflicts").json()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["class_id"], class_entry["id"])
        self.assertEqual(result[0]["availability_id"], availability["id"])
        self.assertEqual(self.request("GET", "/students/me/availability").json()[0]["start_time"], "09:30:00")
        self.request("PUT", f"/students/me/availability/{availability['id']}", json=self.window("availability", start_time="10:00", end_time="11:00"))
        self.assertEqual(self.request("GET", "/students/me/conflicts").json(), [])

    def test_cors_bearer_and_write_preflight(self):
        result = self.client.options("/api/students/me/classes", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["access-control-allow-origin"], "http://localhost:5173")


class MigrationTests(unittest.TestCase):
    def test_upgrade_downgrade_and_seed_idempotence(self):
        # Use a workspace temporary directory to respect the Windows sandbox.
        with TemporaryDirectory(dir=BACKEND_DIR) as directory:
            url = "sqlite:///" + str(Path(directory) / "test.db")
            with patch.dict(os.environ, {"DATABASE_URL": url}):
                config = Config(str(BACKEND_DIR / "alembic.ini"))
                command.upgrade(config, "head")
                engine, factory = create_session_factory(url)
                self.assertIn("users", inspect(engine).get_table_names())
                engine.dispose()
                from app.seed import main as seed
                with patch("sys.argv", ["seed", "--demo"]), patch("getpass.getpass", return_value=PASSWORD):
                    seed()
                    seed()
                with factory() as db:
                    self.assertEqual(len(list(db.scalars(select(User)))), 2)
                engine.dispose()
                command.check(config)
                command.downgrade(config, "base")
                engine, _ = create_session_factory(url)
                self.assertNotIn("users", inspect(engine).get_table_names())
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
