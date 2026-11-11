from datetime import date, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_db, student_only, supervisor_only
from app.models import ScheduleEvent, User
from app.schemas.scheduling import RunDetail, StudentPreview
from app.schemas.workflows import (AddShiftInput, DecisionInput, LeaveStatus, PublishInput,
    ReassignInput, TimeOffInput, TimeOffOut, VersionInput)
from app.services import schedule_editor, scheduling, time_off

router = APIRouter(prefix="/api")


@router.post("/students/me/time-off", response_model=TimeOffOut, status_code=201)
def submit(data: TimeOffInput, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return time_off.submit(db, user, data)


@router.get("/students/me/time-off", response_model=list[TimeOffOut])
def student_requests(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return time_off.list_requests(db, user)


@router.get("/students/me/time-off/{request_id}", response_model=TimeOffOut)
def student_request(request_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return time_off.owned_request(db, user, request_id)


@router.post("/students/me/time-off/{request_id}/cancel", response_model=TimeOffOut)
def cancel(request_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return time_off.cancel(db, user, request_id)


@router.get("/supervisor/time-off", response_model=list[TimeOffOut])
def requests(status: LeaveStatus | None = None, start_date: date | None = None, end_date: date | None = None,
             user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return time_off.list_requests(db, user, status, start_date, end_date)


@router.get("/supervisor/time-off/{request_id}", response_model=TimeOffOut)
def request(request_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return time_off.owned_request(db, user, request_id)


@router.post("/supervisor/time-off/{request_id}/decision", response_model=TimeOffOut)
def decide(request_id: int, data: DecisionInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return time_off.decide(db, user, request_id, data)


@router.get("/supervisor/schedule-conflicts")
def conflicts(user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return time_off.assignment_conflicts(db, user.department_id)


@router.get("/supervisor/schedules/{run_id}/validation")
def validation(run_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return schedule_editor.validation_issues(db, scheduling.owned_run(db, user.department_id, run_id))


@router.post("/supervisor/schedules/{run_id}/shifts", response_model=RunDetail, status_code=201)
def add(run_id: int, data: AddShiftInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.run_detail(schedule_editor.edit(db, user, run_id, data, "add"))


@router.patch("/supervisor/schedules/{run_id}/shifts/{shift_id}", response_model=RunDetail)
def reassign(run_id: int, shift_id: int, data: ReassignInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.run_detail(schedule_editor.edit(db, user, run_id, data, "reassign", shift_id))


@router.post("/supervisor/schedules/{run_id}/shifts/{shift_id}/remove", response_model=RunDetail)
def remove(run_id: int, shift_id: int, data: VersionInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.run_detail(schedule_editor.edit(db, user, run_id, data, "remove", shift_id))


@router.post("/supervisor/schedules/{run_id}/publish", response_model=RunDetail)
def publish(run_id: int, data: PublishInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.run_detail(schedule_editor.publish(db, user, run_id, data))


@router.get("/supervisor/schedules/{run_id}/events")
def events(run_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    scheduling.owned_run(db, user.department_id, run_id)
    return [{"id": e.id, "actor_id": e.actor_id, "action": e.action, "created_at": e.created_at.replace(tzinfo=timezone.utc),
             "details": e.details} for e in db.scalars(select(ScheduleEvent).where(ScheduleEvent.schedule_run_id == run_id).order_by(ScheduleEvent.id))]


@router.get("/students/me/draft-schedule", response_model=StudentPreview)
def draft(week_start: date | None = None, user: User = Depends(student_only), db: Session = Depends(get_db)):
    if week_start and week_start.weekday() != 0:
        from fastapi import HTTPException
        raise HTTPException(422, "Week start must be Monday")
    return scheduling.student_preview(db, user, week_start, draft=True)
