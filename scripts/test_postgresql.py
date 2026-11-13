"""Run regression tests against a disposable LOCAL PostgreSQL container.

Uses random loopback port, password and schema names. Removes only the container
created by this invocation. No existing database or AWS resource is accessed.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="postgres:16", help="Override with a digest for exact repeatability")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = "campusshift-test-" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    env = {**os.environ, "POSTGRES_PASSWORD": password}
    created = False
    try:
        result = subprocess.run(["docker", "run", "-d", "--name", name, "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB=campusshift_test", "-p", "127.0.0.1::5432", args.image], env=env, capture_output=True, text=True)
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            return result.returncode
        created = True
        info = json.loads(subprocess.check_output(["docker", "inspect", name], text=True))[0]
        port = info["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
        print("Local PostgreSQL test image:", info["Image"], flush=True)
        import psycopg
        for attempt in range(60):
            try:
                with psycopg.connect(host="127.0.0.1", port=int(port), user="postgres", password=password, dbname="campusshift_test", connect_timeout=2) as connection:
                    version = connection.execute("SELECT version()").fetchone()[0]
                    print(version, flush=True)
                break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            raise RuntimeError("Local PostgreSQL did not become ready")
        test_env = {**os.environ, "TEST_POSTGRESQL_URL": f"postgresql+psycopg://postgres:{password}@127.0.0.1:{port}/campusshift_test"}
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=root / "backend", env=test_env)
        if result.returncode:
            return result.returncode
        # Verify the real backup/restore script using synthetic migrated data.
        sys.path.insert(0, str(root / "backend"))
        os.environ.update(DATABASE_URL=test_env["TEST_POSTGRESQL_URL"], APP_ENV="test")
        from alembic import command
        from alembic.config import Config
        from app.db.session import create_session_factory
        from app.seed_cloud_demo import populate
        from datetime import date, timedelta
        command.upgrade(Config(str(root / "backend/alembic.ini")), "head")
        engine, factory = create_session_factory(test_env["TEST_POSTGRESQL_URL"])
        with factory() as db:
            day = date.today()
            populate(db, secrets.token_urlsafe(24), day - timedelta(days=day.weekday() + 14))
        engine.dispose()
        subprocess.run(["docker", "cp", str(root / "scripts/database_backup.sh"), name + ":/tmp/database_backup.sh"], check=True)

        def script(database, *arguments, expected=0):
            result = subprocess.run(["docker", "exec", "-e", "PGHOST=/var/run/postgresql", "-e", "PGUSER=postgres", "-e", f"PGDATABASE={database}", "-e", "PGSSLMODE=disable", name, "bash", "/tmp/database_backup.sh", *arguments], capture_output=True, text=True)
            if result.returncode != expected:
                raise RuntimeError("Backup/restore script failed: " + result.stderr)

        script("campusshift_test", "backup", "/tmp/demo.dump")
        script("campusshift_test", "backup", "/tmp/demo.dump", expected=1)
        script("campusshift_test", "restore", "/tmp/demo.dump", "--approve-empty-target-restore", expected=1)
        subprocess.run(["docker", "exec", name, "createdb", "-U", "postgres", "campusshift_restore"], check=True)
        script("campusshift_restore", "restore", "/tmp/demo.dump", expected=1)
        script("campusshift_restore", "restore", "/tmp/demo.dump", "--approve-empty-target-restore")
        sql = "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM schedule_runs), (SELECT count(*) FROM assigned_shifts), (SELECT count(*) FROM attendance_records), (SELECT count(*) FROM attendance_events)"
        counts = []
        for database in ("campusshift_test", "campusshift_restore"):
            counts.append(subprocess.check_output(["docker", "exec", name, "psql", "-U", "postgres", "-d", database, "-Atc", sql], text=True).strip())
        if counts[0] != counts[1] or counts[0].split("|")[3] != "2":
            raise RuntimeError("Restored synthetic record counts do not match")
        print("PASS backup/restore, overwrite refusal, populated-target refusal and approval gate; synthetic counts:", counts[0], flush=True)
        return 0
    finally:
        if created:
            subprocess.run(["docker", "rm", "-f", name], check=True, stdout=subprocess.DEVNULL)
            print("Removed this invocation's disposable PostgreSQL container.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
