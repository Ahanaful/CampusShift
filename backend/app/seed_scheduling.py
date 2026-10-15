"""Reproducible, opt-in Phase 3 demonstration in its own local department."""

import argparse
import getpass
from datetime import time

from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hasher
from app.db.session import create_session_factory
from app.models import (Availability, ClassSchedule, Department, LocationEligibility,
                        StaffingRequirement, User, WorkLocation)
from app.schemas import Register

DEPARTMENT_NAME = "Scheduling Demo"
SUPERVISOR_EMAIL = "scheduling.supervisor@example.com"
STUDENTS = (
    ("Avery Chen", "avery.schedule@example.com", 10, True, (0, 1, 2, 3, 4)),
    ("Jordan Rivera", "jordan.schedule@example.com", 12, True, (0, 1, 2, 3, 4)),
    ("Sam Patel", "sam.schedule@example.com", 8, True, (1, 3, 6)),
    ("Zero Hours", "zero.schedule@example.com", 0, True, (0, 1, 2, 3, 4)),
    ("Inactive Demo", "inactive.schedule@example.com", 20, False, (0, 1, 2, 3, 4)),
)


def seed_data(db, password):
    department = db.scalar(select(Department).where(Department.name == DEPARTMENT_NAME))
    if department is None:
        department = Department(name=DEPARTMENT_NAME, description="Reproducible weekly staffing example", timezone="America/Chicago")
        db.add(department)
        db.flush()

    def account(name, email, role, hours, active=True):
        user = db.scalar(select(User).where(User.email == email))
        if user:
            if user.department_id != department.id or user.role != role:
                raise ValueError(f"Demo email {email} belongs to another department or role; no data was changed.")
            return user
        user = User(full_name=name, email=email, password_hash=hasher.hash(password), role=role,
                    department_id=department.id, max_weekly_hours=hours, is_active=active)
        db.add(user)
        db.flush()
        return user

    account("Scheduling Supervisor", SUPERVISOR_EMAIL, "supervisor", 20)
    people = []
    for name, email, hours, active, weekdays in STUDENTS:
        user = account(name, email, "student", hours, active)
        people.append(user)
        for day in weekdays:
            if not db.scalar(select(Availability.id).where(Availability.student_id == user.id, Availability.day_of_week == day).limit(1)):
                db.add(Availability(student_id=user.id, day_of_week=day,
                                    start_time=time(12 if day == 6 else 9), end_time=time(14 if day == 6 else 16)))
    for student, day, start, end, course in [(people[0], 0, 10, 11, "Cloud Computing"), (people[1], 1, 9, 10, "Networks")]:
        if not db.scalar(select(ClassSchedule.id).where(ClassSchedule.student_id == student.id, ClassSchedule.course_name == course).limit(1)):
            db.add(ClassSchedule(student_id=student.id, day_of_week=day, course_name=course, start_time=time(start), end_time=time(end)))
    work_locations = []
    for name in ("Library Front Desk", "Study Support"):
        location = db.scalar(select(WorkLocation).where(WorkLocation.department_id == department.id, WorkLocation.name == name))
        if location is None:
            location = WorkLocation(department_id=department.id, name=name, description="Phase 3 demo work location", is_active=True)
            db.add(location)
            db.flush()
            # Sam is trained only for front-desk work; others can work both.
            location.eligibility = [LocationEligibility(student_id=person.id) for person in people
                                    if name == "Library Front Desk" or person != people[2]]
        work_locations.append(location)
    demand = [(work_locations[0], day, 9, 12, 2) for day in range(5)]
    demand += [(work_locations[1], day, 12, 15, 1) for day in (0, 2, 4)]
    demand += [(work_locations[1], 1, 9, 12, 1), (work_locations[0], 6, 12, 14, 1)]
    for location, day, start, end, count in demand:
        if not db.scalar(select(StaffingRequirement.id).where(StaffingRequirement.location_id == location.id,
                                                             StaffingRequirement.day_of_week == day).limit(1)):
            db.add(StaffingRequirement(department_id=department.id, location_id=location.id, day_of_week=day,
                                      start_time=time(start), end_time=time(end), required_count=count, is_active=True))
    db.commit()


def main():
    parser = argparse.ArgumentParser(description="Seed an isolated local scheduling demo without resetting existing data")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    if not args.demo or not settings.database_url.startswith("sqlite:"):
        parser.error("Requires --demo and a local SQLite DATABASE_URL")
    password = getpass.getpass("Password for new demo accounts (12–128 characters): ")
    Register(full_name="Demo", email=SUPERVISOR_EMAIL, department_id=1, password=password)
    engine, factory = create_session_factory(settings.database_url)
    try:
        with factory() as db:
            seed_data(db, password)
    finally:
        engine.dispose()
    print(f"Scheduling demo ready. Supervisor: {SUPERVISOR_EMAIL}")
    print("Student: avery.schedule@example.com (Jordan and Sam accounts are also available).")
    print("Existing passwords and edited data were preserved. Generate the week beginning 2026-10-19.")


if __name__ == "__main__":
    main()
