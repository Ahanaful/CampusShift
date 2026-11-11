"""Leave transitions and live supervisor notifications. No assignment mutation."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import AssignedShift, ScheduleRun, TimeOffRequest, User
from app.services.scheduling import reserve_write


def list_requests(db, user, status=None, start_date=None, end_date=None):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "Filter start date must precede end date")
    query = select(TimeOffRequest).where(TimeOffRequest.department_id == user.department_id)
    if user.role == "student":
        query = query.where(TimeOffRequest.student_id == user.id)
    if status:
        query = query.where(TimeOffRequest.status == status)
    if start_date:
        query = query.where(TimeOffRequest.end_date >= start_date)
    if end_date:
        query = query.where(TimeOffRequest.start_date <= end_date)
    return list(db.scalars(query.order_by(TimeOffRequest.created_at.desc(), TimeOffRequest.id.desc())))


def owned_request(db, user, request_id):
    query = select(TimeOffRequest).where(TimeOffRequest.id == request_id, TimeOffRequest.department_id == user.department_id)
    if user.role == "student":
        query = query.where(TimeOffRequest.student_id == user.id)
    item = db.scalar(query.execution_options(populate_existing=True))
    if item is None:
        raise HTTPException(404, "Time-off request not found")
    return item


def submit(db, student, data):
    item = TimeOffRequest(student_id=student.id, department_id=student.department_id, **data.model_dump(), status="pending")
    db.add(item)
    db.commit()
    return item


def cancel(db, student, request_id):
    reserve_write(db)
    item = owned_request(db, student, request_id)
    if item.status != "pending":
        raise HTTPException(409, "Only pending requests can be cancelled")
    item.status = "cancelled"
    item.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    return item


def decide(db, supervisor, request_id, data):
    reserve_write(db)
    item = owned_request(db, supervisor, request_id)
    if item.student_id == supervisor.id:
        raise HTTPException(403, "You cannot review your own request")
    if item.status != "pending":
        raise HTTPException(409, "This request has already been decided or cancelled. Refresh the list.")
    item.status = data.status
    item.decision_note = data.decision_note
    item.reviewer_id = supervisor.id
    item.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return item


def assignment_conflicts(db, department_id):
    rows = db.execute(select(TimeOffRequest, AssignedShift, ScheduleRun)
        .join(AssignedShift, AssignedShift.student_id == TimeOffRequest.student_id)
        .join(ScheduleRun, ScheduleRun.id == AssignedShift.schedule_run_id)
        .where(TimeOffRequest.department_id == department_id, ScheduleRun.department_id == department_id,
               TimeOffRequest.status == "approved", ScheduleRun.status.in_(["draft", "published"]),
               AssignedShift.shift_date >= TimeOffRequest.start_date, AssignedShift.shift_date <= TimeOffRequest.end_date)
        .order_by(AssignedShift.shift_date, ScheduleRun.id, AssignedShift.id))
    return [{"request_id": leave.id, "run_id": run.id, "run_status": run.status, "shift_id": shift.id,
             "student_id": shift.student_id, "student_name": shift.student_name, "shift_date": shift.shift_date,
             "start_time": shift.start_time, "end_time": shift.end_time, "location_name": shift.location_name}
            for leave, shift, run in rows]
