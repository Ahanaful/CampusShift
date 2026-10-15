"""Explicit local demo setup; never called during application startup."""

import argparse
import getpass

from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hasher
from app.db.session import create_session_factory
from app.models import Department, User
from app.schemas import Register


def main():
    parser = argparse.ArgumentParser(description="Create local demo accounts without overwriting existing users.")
    parser.add_argument("--demo", action="store_true", help="Confirm local demo initialization")
    parser.add_argument("--department-only", action="store_true", help="Initialize the demo department without accounts")
    args = parser.parse_args()
    settings = Settings.from_env()
    if not args.demo or not settings.database_url.startswith("sqlite:"):
        parser.error("This command requires --demo and a local SQLite DATABASE_URL.")
    password = None
    if not args.department_only:
        password = getpass.getpass("Demo password (12–128 characters; used for both accounts): ")
        Register(email="student@example.com", password=password, full_name="Demo Student", department_id=1)
    engine, factory = create_session_factory(settings.database_url)
    with factory() as db:
        department = db.scalar(select(Department).where(Department.name == "Campus Library"))
        if not department:
            department = Department(name="Campus Library", description="Library student employee team")
            db.add(department)
            db.flush()
        if args.department_only:
            db.commit()
            print("Local demo department ready. No accounts were created.")
            engine.dispose()
            return
        for email, name, role in (("supervisor@example.com", "Demo Supervisor", "supervisor"),
                                  ("student@example.com", "Demo Student", "student")):
            if db.scalar(select(User).where(User.email == email)):
                print(f"Skipped existing account: {email}")
                continue
            db.add(User(email=email, full_name=name, role=role, department_id=department.id,
                        password_hash=hasher.hash(password), max_weekly_hours=20))
            print(f"Creating {role}: {email}")
        db.commit()
    engine.dispose()
    print("Local demo ready. Existing passwords were not changed.")


if __name__ == "__main__":
    main()
