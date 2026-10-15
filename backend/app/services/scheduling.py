"""Translate database snapshots to pure scheduler inputs and persist new drafts."""

from datetime import time

from fastapi import HTTPException
from sqlalchemy import select, text

from app.models import (AssignedShift, Department,
                        LocationEligibility, ScheduleRun, StaffingRequirement,
                        UnfilledRequirement, User, WorkLocation)
from scheduler.engine import (ALGORITHM_VERSION, Requirement, Student, Window, generate)


def update_student_status(db, supervisor, student_id, is_active):
    from app.services.accounts import department_student
    student = department_student(db, supervisor, student_id)
    student.is_active = is_active
    db.commit()
    return student


def reserve_write(db):
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def location(db, department_id, location_id):
    item = db.scalar(select(WorkLocation).where(WorkLocation.id == location_id, WorkLocation.department_id == department_id))
    if item is None:
        raise HTTPException(404, "Work location not found.")
    return item


def location_data(item):
    return {"id": item.id, "department_id": item.department_id, "name": item.name,
            "description": item.description, "is_active": item.is_active,
            "eligible_student_ids": sorted(entry.student_id for entry in item.eligibility)}


def locations(db, department_id):
    return [location_data(item) for item in db.scalars(select(WorkLocation)
            .where(WorkLocation.department_id == department_id).order_by(WorkLocation.name, WorkLocation.id))]


def save_location(db, department_id, data, location_id=None):
    reserve_write(db)
    item = location(db, department_id, location_id) if location_id else WorkLocation(department_id=department_id)
    ids = set(data.eligible_student_ids)
    valid = set(db.scalars(select(User.id).where(User.id.in_(ids), User.role == "student", User.department_id == department_id)))
    if ids != valid:
        raise HTTPException(422, "Eligible employees must be students in your department.")
    for key, value in data.model_dump(exclude={"eligible_student_ids"}).items():
        setattr(item, key, value)
    if location_id:
        # Remove only changed associations to avoid duplicate composite keys.
        existing = {entry.student_id: entry for entry in item.eligibility}
        for student_id in set(existing) - ids:
            item.eligibility.remove(existing[student_id])
        for student_id in ids - set(existing):
            item.eligibility.append(LocationEligibility(student_id=student_id))
    else:
        item.eligibility = [LocationEligibility(student_id=student_id) for student_id in sorted(ids)]
        db.add(item)
    db.commit()
    return location_data(item)


def requirements(db, department_id):
    return list(db.scalars(select(StaffingRequirement).where(StaffingRequirement.department_id == department_id)
                           .order_by(StaffingRequirement.day_of_week, StaffingRequirement.start_time, StaffingRequirement.id)))


def owned_requirement(db, department_id, requirement_id):
    item = db.scalar(select(StaffingRequirement).where(StaffingRequirement.id == requirement_id,
                     StaffingRequirement.department_id == department_id))
    if item is None:
        raise HTTPException(404, "Staffing requirement not found.")
    return item


def save_requirement(db, department_id, data, requirement_id=None):
    reserve_write(db)
    item = owned_requirement(db, department_id, requirement_id) if requirement_id else None
    work_location = location(db, department_id, data.location_id)
    if data.is_active and not work_location.is_active:
        raise HTTPException(422, "Choose an active location for an active requirement.")
    if data.is_active:
        query = select(StaffingRequirement.id).where(StaffingRequirement.department_id == department_id,
            StaffingRequirement.location_id == data.location_id, StaffingRequirement.day_of_week == data.day_of_week,
            StaffingRequirement.is_active.is_(True), StaffingRequirement.start_time < data.end_time,
            StaffingRequirement.end_time > data.start_time)
        if item:
            query = query.where(StaffingRequirement.id != item.id)
        if db.scalar(query) is not None:
            raise HTTPException(409, "Active staffing windows overlap at this location. Edit or deactivate the existing requirement first.")
    if item is None:
        item = StaffingRequirement(department_id=department_id)
        db.add(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return item


def delete_requirement(db, department_id, requirement_id):
    reserve_write(db)
    item = owned_requirement(db, department_id, requirement_id)
    if db.scalar(select(AssignedShift.id).where(AssignedShift.requirement_id == requirement_id).limit(1)) is not None or db.scalar(
            select(UnfilledRequirement.id).where(UnfilledRequirement.staffing_requirement_id == requirement_id).limit(1)) is not None:
        raise HTTPException(409, "This requirement is used by a saved draft. Deactivate it to preserve schedule history.")
    db.delete(item)
    db.commit()


def minutes(value):
    return value.hour * 60 + value.minute


def clock(value):
    return time(value // 60, value % 60)


def list_runs(db, department_id):
    return list(db.scalars(select(ScheduleRun).where(ScheduleRun.department_id == department_id)
                           .order_by(ScheduleRun.created_at.desc(), ScheduleRun.id.desc())))


def owned_run(db, department_id, run_id):
    run = db.scalar(select(ScheduleRun).where(ScheduleRun.id == run_id, ScheduleRun.department_id == department_id))
    if run is None:
        raise HTTPException(404, "Schedule draft not found.")
    return run


def generate_run(db, supervisor, week_start):
    # One write transaction protects the input snapshot and the entire saved run.
    reserve_write(db)
    department_id = supervisor.department_id
    department = db.get(Department, department_id)
    people = list(db.scalars(select(User).where(User.department_id == department_id, User.role == "student").order_by(User.id)))
    work_locations = list(db.scalars(select(WorkLocation).where(WorkLocation.department_id == department_id, WorkLocation.is_active.is_(True))))
    location_map = {item.id: item for item in work_locations}
    staffing = [r for r in requirements(db, department_id) if r.is_active and r.location_id in location_map]
    previous = db.scalar(select(ScheduleRun).where(ScheduleRun.department_id == department_id, ScheduleRun.week_start < week_start)
                         .order_by(ScheduleRun.week_start.desc(), ScheduleRun.id.desc()).limit(1))
    history = previous.summary.get("employee_minutes", {}) if previous else {}
    inputs = tuple(Student(
        id=person.id, department_id=person.department_id, max_minutes=person.max_weekly_hours * 60,
        active=person.is_active, prior_minutes=history.get(str(person.id), 0),
        eligible_locations=frozenset(item.id for item in work_locations if any(e.student_id == person.id for e in item.eligibility)),
        classes=tuple(Window(w.day_of_week, minutes(w.start_time), minutes(w.end_time)) for w in person.classes),
        availability=tuple(Window(w.day_of_week, minutes(w.start_time), minutes(w.end_time)) for w in person.availability),
    ) for person in people)
    demand = tuple(Requirement(r.id, r.department_id, r.location_id, r.day_of_week,
                              minutes(r.start_time), minutes(r.end_time), r.required_count) for r in staffing)
    try:
        result = generate(department_id, week_start, inputs, demand)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    people_map = {p.id: p for p in people}
    summary = {**result.summary, "timezone": department.timezone,
               "history_run_id": previous.id if previous else None,
               "employee_names": {str(p.id): p.full_name for p in people},
               "input_snapshot": {
                   "students": [{"id": s.id, "active": s.active, "max_minutes": s.max_minutes,
                       "eligible_locations": sorted(s.eligible_locations), "prior_minutes": s.prior_minutes,
                       "classes": [[w.day, w.start, w.end] for w in s.classes],
                       "availability": [[w.day, w.start, w.end] for w in s.availability]} for s in inputs],
                   "requirements": [{"id": r.id, "location_id": r.location_id, "day": r.day,
                       "start": r.start, "end": r.end, "count": r.count} for r in demand]}}
    run = ScheduleRun(department_id=department_id, week_start=week_start, created_by=supervisor.id,
                      algorithm_version=ALGORITHM_VERSION, summary=summary, status="draft")
    db.add(run)
    try:
        db.flush()
        for assignment in result.assignments:
            run.shifts.append(AssignedShift(student_id=assignment.student_id, requirement_id=assignment.requirement_id,
                location_id=assignment.location_id, shift_date=assignment.shift_date, start_time=clock(assignment.start),
                end_time=clock(assignment.end), duration_minutes=assignment.end - assignment.start, status="draft",
                student_name=people_map[assignment.student_id].full_name, location_name=location_map[assignment.location_id].name))
        for gap in result.unfilled:
            run.unfilled.append(UnfilledRequirement(staffing_requirement_id=gap.requirement_id, location_id=gap.location_id,
                shift_date=gap.shift_date, start_time=clock(gap.start), end_time=clock(gap.end), missing_count=gap.missing_count,
                reason=gap.reason, location_name=location_map[gap.location_id].name))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return run


def run_detail(run):
    return {"id": run.id, "department_id": run.department_id, "week_start": run.week_start,
            "status": run.status, "created_by": run.created_by, "created_at": run.created_at,
            "algorithm_version": run.algorithm_version, "summary": run.summary,
            "shifts": sorted(run.shifts, key=lambda s: (s.shift_date, s.start_time, s.location_id, s.student_id)),
            "unfilled": sorted(run.unfilled, key=lambda u: (u.shift_date, u.start_time, u.location_id, u.id))}


def student_preview(db, student, week_start=None):
    query = select(ScheduleRun).where(ScheduleRun.department_id == student.department_id)
    if week_start:
        query = query.where(ScheduleRun.week_start == week_start)
    run = db.scalar(query.order_by(ScheduleRun.created_at.desc(), ScheduleRun.id.desc()).limit(1))
    if run is None:
        return {"run_id": None, "week_start": week_start, "status": "draft", "timezone": db.get(Department, student.department_id).timezone,
                "assigned_hours": 0, "shifts": []}
    shifts = sorted((s for s in run.shifts if s.student_id == student.id), key=lambda s: (s.shift_date, s.start_time, s.id))
    return {"run_id": run.id, "week_start": run.week_start, "status": "draft", "timezone": run.summary["timezone"],
            "assigned_hours": sum(s.duration_minutes for s in shifts) / 60, "shifts": shifts}
