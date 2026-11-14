"""Real local Uvicorn restart and backup restore, using fictional disposable data."""
from contextlib import closing, contextmanager
import importlib.util
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import httpx

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sqlite_backup", ROOT / "scripts/sqlite_backup.py")
backup_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup_tool)


@contextmanager
def server(database):
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + str(database), "APP_ENV": "test",
           "JWT_SECRET": "fictional-local-test-only-secret-at-least-32-bytes", "CORS_ORIGINS": ""}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
                                "--port", str(port)], cwd=ROOT / "backend", env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=2) as client:
            deadline = time.monotonic() + 15
            while True:
                try:
                    if client.get("/api/ready").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Disposable local Uvicorn did not become ready")
                time.sleep(0.05)
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


class SQLiteReleaseTests(unittest.TestCase):
    def test_registration_class_survives_process_restart_and_backup_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "fictional.sqlite3"
            env = {**os.environ, "DATABASE_URL": "sqlite:///" + str(database), "APP_ENV": "test"}
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend",
                           env=env, check=True, capture_output=True)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("INSERT INTO departments (id,name,description,timezone) VALUES (1,'Fictional Lab','','America/Chicago')")
                connection.commit()
            credentials = {"email": "restart.student@example.com", "password": "fictional-restart-only-password"}

            def login(client):
                response = client.post("/api/auth/login", json=credentials)
                self.assertEqual(response.status_code, 200)
                return {"Authorization": "Bearer " + response.json()["access_token"]}

            with server(database) as client:
                response = client.post("/api/auth/register", json={**credentials, "full_name": "Fictional Student", "department_id": 1})
                self.assertEqual(response.status_code, 201)
                auth = login(client)
                response = client.post("/api/students/me/classes", headers=auth,
                                       json={"course_name": "Recovery Lab", "day_of_week": 0,
                                             "start_time": "09:00", "end_time": "10:00"})
                self.assertEqual(response.status_code, 201)
                row_id = response.json()["id"]
                self.assertEqual(client.get("/api/supervisor/employees", headers=auth).status_code, 403)

            with server(database) as client:
                rows = client.get("/api/students/me/classes", headers=login(client)).json()
                self.assertTrue(any(row["id"] == row_id for row in rows))

            snapshot = backup_tool.backup(database, directory / "backups")
            restored = backup_tool.restore(snapshot, directory / "recovered" / "restored.sqlite3")
            with server(restored) as client:
                rows = client.get("/api/students/me/classes", headers=login(client)).json()
                self.assertTrue(any(row["id"] == row_id and row["course_name"] == "Recovery Lab" for row in rows))
