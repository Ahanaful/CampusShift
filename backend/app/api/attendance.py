from datetime import date
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_db, student_only, supervisor_only
from app.models import AttendanceEvent, User
from app.schemas.attendance import ClockInInput, CorrectionDecision, CorrectionInput, CorrectionStatus, RecordStatus
from app.schemas import Input
from app.services import attendance

router = APIRouter(prefix="/api")


@router.get("/students/me/attendance")
def student_attendance(request: Request, response: Response, user: User = Depends(student_only), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return attendance.report(db, user, request.app.state.settings)


@router.post("/students/me/attendance/clock-in", status_code=201)
def clock_in(data: ClockInInput, request: Request, user: User = Depends(student_only), db: Session = Depends(get_db)):
    record = attendance.clock_in(db, user, data, request.app.state.settings)
    return attendance.record_data(record, attendance.department_zone(db, user), request.app.state.settings, record.updated_at)


@router.post("/students/me/attendance/{record_id}/clock-out")
def clock_out(record_id: int, data: Input, request: Request, user: User = Depends(student_only), db: Session = Depends(get_db)):
    record = attendance.clock_out(db, user, record_id)
    return attendance.record_data(record, attendance.department_zone(db, user), request.app.state.settings, record.updated_at)


@router.post("/students/me/attendance/corrections", status_code=201)
def correction(data: CorrectionInput, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return attendance.correction_data(attendance.request_correction(db, user, data))


@router.get("/students/me/attendance/corrections")
def student_corrections(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return [attendance.correction_data(item) for item in attendance.list_corrections(db, user)]


@router.get("/supervisor/attendance")
def supervisor_attendance(request: Request, response: Response, start_date: date | None = None, end_date: date | None = None,
        student_id: int | None = Query(default=None, gt=0), status: RecordStatus | None = None,
        user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return attendance.report(db, user, request.app.state.settings, start_date, end_date, status, student_id)


@router.get("/supervisor/attendance/export.csv")
def export(request: Request, start_date: date | None = None, end_date: date | None = None,
        student_id: int | None = Query(default=None, gt=0), status: RecordStatus | None = None,
        user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    report = attendance.report(db, user, request.app.state.settings, start_date, end_date, status, student_id)
    attendance.logger.info("Attendance CSV export actor=%s department=%s rows=%s", user.id, user.department_id, len(report["records"]))
    return Response(attendance.csv_export(report), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="campusshift-attendance.csv"', "Cache-Control": "no-store"})


@router.get("/supervisor/attendance/corrections")
def corrections(status: CorrectionStatus | None = None, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return [attendance.correction_data(item) for item in attendance.list_corrections(db, user, status)]


@router.post("/supervisor/attendance/corrections/{correction_id}/decision")
def decide(correction_id: int, data: CorrectionDecision, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return attendance.correction_data(attendance.decide(db, user, correction_id, data))


def history(db, user, record_id):
    attendance.scoped_record(db, user, record_id)
    return [{"id": event.id, "actor_id": event.actor_id, "action": event.action,
        "occurred_at": event.occurred_at, "details": event.details}
        for event in db.scalars(select(AttendanceEvent).where(AttendanceEvent.attendance_record_id == record_id).order_by(AttendanceEvent.id))]


@router.get("/students/me/attendance/{record_id}/audit")
def student_audit(record_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return history(db, user, record_id)


@router.get("/supervisor/attendance/{record_id}/audit")
def supervisor_audit(record_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return history(db, user, record_id)
