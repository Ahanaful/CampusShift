"""Explicit fictional sandbox fixture; never runs at startup or copies SQLite data."""
import argparse
from datetime import date, timedelta
import getpass
from sqlalchemy import select
from app.core.config import Settings
from app.core.attendance_time import now_utc, shift_instants, zone
from app.db.session import create_session_factory
from app.models import AttendanceRecord, Department, ScheduleRun, User
from app.schemas import Register
from app.schemas.workflows import PublishInput
from app.schemas.attendance import CorrectionInput, CorrectionDecision
from app.seed_scheduling import DEPARTMENT_NAME, SUPERVISOR_EMAIL, seed_data
from app.services import attendance, scheduling, schedule_editor


def populate(db, password, week_start):
    seed_data(db, password)  # Idempotent isolated fictional department, classes and staffing.
    supervisor = db.scalar(select(User).where(User.email == SUPERVISOR_EMAIL))
    department = db.scalar(select(Department).where(Department.name == DEPARTMENT_NAME))
    run = db.scalar(select(ScheduleRun).where(ScheduleRun.department_id == department.id,
                    ScheduleRun.week_start == week_start, ScheduleRun.status == "published"))
    if run is None:
        run = scheduling.generate_run(db, supervisor, week_start)
        run = schedule_editor.publish(db, supervisor, run.id, PublishInput(expected_version=run.version, acknowledge_uncovered=True))
    made = 0
    for shift in sorted(run.shifts, key=lambda item: item.id)[:2]:
        if db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.assigned_shift_id == shift.id)):
            continue
        start, end = shift_instants(shift, department.timezone)
        if end >= now_utc():
            continue
        student = db.get(User, shift.student_id)
        proposal = attendance.request_correction(db, student, CorrectionInput(assigned_shift_id=shift.id,
            proposed_clock_in=start, proposed_clock_out=end, reason="Fictional sandbox demonstration: simulated historical attendance"))
        attendance.decide(db, supervisor, proposal.id, CorrectionDecision(status="approved", reviewer_note="Synthetic demo record; no actual employee work"))
        made += 1
    return run.id, made


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-demo", action="store_true", required=True)
    parser.add_argument("--week-start", type=date.fromisoformat)
    args = parser.parse_args()
    password = getpass.getpass("Password for NEW fictional accounts (existing passwords preserved): ")
    Register(full_name="Demo", email=SUPERVISOR_EMAIL, department_id=1, password=password)
    engine, factory = create_session_factory(Settings.from_env().database_url)
    try:
        today = now_utc().astimezone(zone("America/Chicago")).date()
        monday = args.week_start or today - timedelta(days=today.weekday() + 7)
        if monday.weekday() or monday + timedelta(days=7) > today:
            parser.error("Choose a completed Monday week for historical synthetic attendance")
        with factory() as db:
            run_id, count = populate(db, password, monday)
        print(f"Fictional published schedule {run_id} ready; {count} synthetic corrected attendance records added.")
        print(f"Supervisor: {SUPERVISOR_EMAIL}. No real student records imported.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
