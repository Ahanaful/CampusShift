"""Attendance persistence, authorization, UTC intervals, and auditable decisions."""
import csv
import io
import logging
from datetime import datetime, time, timedelta
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from app.core.attendance_time import UTC, local_to_utc, now_utc, shift_instants, zone
from app.models import (AssignedShift, AttendanceCorrection, AttendanceEvent, AttendanceRecord,
                        Department, ScheduleRun)
from app.services.scheduling import reserve_write

logger = logging.getLogger(__name__)


def department_zone(db, user):
    return db.get(Department, user.department_id).timezone


def scoped_shift(db, user, shift_id, published_only=False):
    query = select(AssignedShift).join(ScheduleRun).where(AssignedShift.id == shift_id,
        ScheduleRun.department_id == user.department_id, ScheduleRun.status == "published" if published_only else ScheduleRun.status.in_(["published", "archived"]))
    if user.role == "student":
        query = query.where(AssignedShift.student_id == user.id)
    shift = db.scalar(query)
    if shift is None:
        logger.warning("Attendance shift access denied actor=%s shift=%s", user.id, shift_id)
        raise HTTPException(404, "An eligible published shift belonging to you was not found")
    return shift


def scoped_record(db, user, record_id):
    query = select(AttendanceRecord).where(AttendanceRecord.id == record_id, AttendanceRecord.department_id == user.department_id)
    if user.role == "student":
        query = query.where(AttendanceRecord.student_id == user.id)
    record = db.scalar(query.execution_options(populate_existing=True))
    if record is None:
        raise HTTPException(404, "Attendance record not found")
    return record


def instants(shift, timezone_name):
    try:
        return shift_instants(shift, timezone_name)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


def no_overlap(db, student_id, start, end=None, exclude_id=None):
    query = select(AttendanceRecord.id).where(AttendanceRecord.student_id == student_id,
        AttendanceRecord.clock_in_at.is_not(None), or_(AttendanceRecord.clock_out_at.is_(None), AttendanceRecord.clock_out_at > start))
    if end:
        query = query.where(AttendanceRecord.clock_in_at < end)
    if exclude_id:
        query = query.where(AttendanceRecord.id != exclude_id)
    if db.scalar(query.limit(1)) is not None:
        raise HTTPException(409, "This attendance interval overlaps another record or an active clock-in")


def snapshot(record):
    return {"clock_in_at": record.clock_in_at.isoformat() if record.clock_in_at else None,
            "clock_out_at": record.clock_out_at.isoformat() if record.clock_out_at else None,
            "status": record.status, "version": record.version}


def audit(db, record, actor, action, now, details):
    db.add(AttendanceEvent(attendance_record_id=record.id, actor_id=actor.id, action=action, occurred_at=now, details=details))
    logger.info("Attendance action=%s actor=%s record=%s", action, actor.id, record.id)


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Attendance changed in another request. Refresh before trying again.") from None
    except Exception:
        db.rollback()
        raise


def clock_in(db, student, data, settings):
    reserve_write(db)
    now = now_utc()
    shift = scoped_shift(db, student, data.assigned_shift_id, published_only=True)
    if not student.is_active:
        raise HTTPException(403, "Your account is inactive for work. Contact your supervisor.")
    if db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.assigned_shift_id == shift.id)) is not None:
        raise HTTPException(409, "Attendance already exists for this shift; use a correction request if needed")
    if db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.student_id == student.id, AttendanceRecord.status == "active")) is not None:
        raise HTTPException(409, "You are already clocked in. Clock out before starting another shift.")
    start, end = instants(shift, department_zone(db, student))
    if now < start - timedelta(minutes=settings.clock_in_early_minutes):
        raise HTTPException(422, f"Too early to clock in. The window opens {settings.clock_in_early_minutes} minutes before the shift.")
    if now > start + timedelta(minutes=settings.clock_in_late_minutes) or now >= end:
        raise HTTPException(422, "The clock-in window has closed. Request a correction if you worked this shift.")
    no_overlap(db, student.id, now)
    record = AttendanceRecord(student_id=student.id, assigned_shift_id=shift.id, department_id=student.department_id,
        clock_in_at=now, status="active", created_at=now, updated_at=now, version=1)
    db.add(record)
    db.flush()
    audit(db, record, student, "clock_in", now, {"before": None, "after": snapshot(record)})
    commit(db)
    return record


def clock_out(db, student, record_id):
    reserve_write(db)
    record = scoped_record(db, student, record_id)
    if record.status != "active":
        raise HTTPException(409, "There is no active clock-in on this record")
    now = now_utc()
    if now <= record.clock_in_at:
        raise HTTPException(409, "Clock-out must follow clock-in. Please try again shortly.")
    no_overlap(db, student.id, record.clock_in_at, now, record.id)
    before = snapshot(record)
    record.clock_out_at = now
    record.status = "completed"
    record.version += 1
    record.updated_at = now
    audit(db, record, student, "clock_out", now, {"before": before, "after": snapshot(record)})
    commit(db)
    return record


def validate_proposal(start, end, shift, timezone_name, now):
    if end <= start:
        raise HTTPException(422, "Corrected clock-out must follow corrected clock-in")
    if end > now:
        raise HTTPException(422, "A correction cannot claim future attendance")
    if end - start > timedelta(hours=24):
        raise HTTPException(422, "Corrected attendance may not exceed 24 elapsed hours")
    local_date = start.astimezone(zone(timezone_name)).date()
    prior_night = (shift.shift_date - local_date).days == 1 and end > instants(shift, timezone_name)[0]
    if local_date != shift.shift_date and not prior_night:
        raise HTTPException(422, "Corrected clock-in must be on the original local shift date, or the preceding night with work continuing past scheduled start")


def request_correction(db, student, data):
    reserve_write(db)
    now = now_utc()
    shift = scoped_shift(db, student, data.assigned_shift_id)
    timezone_name = department_zone(db, student)
    try:
        start = local_to_utc(data.proposed_clock_in, timezone_name, data.clock_in_fold)
        end = local_to_utc(data.proposed_clock_out, timezone_name, data.clock_out_fold)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    validate_proposal(start, end, shift, timezone_name, now)
    record = db.scalar(select(AttendanceRecord).where(AttendanceRecord.assigned_shift_id == shift.id))
    if record is None or record.status == "active":
        _, planned_end = instants(shift, timezone_name)
        if now < planned_end:
            raise HTTPException(422, "For a missed clock-in/out, wait until the scheduled shift has ended; use clock-out for an active shift.")
    if record and db.scalar(select(AttendanceCorrection.id).where(AttendanceCorrection.attendance_record_id == record.id,
                                                               AttendanceCorrection.status == "pending")) is not None:
        raise HTTPException(409, "A pending correction already exists for this record")
    no_overlap(db, student.id, start, end, record.id if record else None)
    if record is None:
        record = AttendanceRecord(student_id=student.id, assigned_shift_id=shift.id, department_id=student.department_id,
            status="missing", created_at=now, updated_at=now, version=1)
        db.add(record)
        db.flush()
    correction = AttendanceCorrection(attendance_record_id=record.id, requested_by=student.id,
        proposed_clock_in=start, proposed_clock_out=end, reason=data.reason, status="pending", base_version=record.version, created_at=now)
    db.add(correction)
    db.flush()
    audit(db, record, student, "correction_requested", now, {"correction_id": correction.id, "original": snapshot(record),
        "proposed_clock_in": start.isoformat(), "proposed_clock_out": end.isoformat()})
    commit(db)
    return correction


def list_corrections(db, user, status=None):
    query = select(AttendanceCorrection).join(AttendanceRecord).where(AttendanceRecord.department_id == user.department_id)
    if user.role == "student":
        query = query.where(AttendanceRecord.student_id == user.id)
    if status:
        query = query.where(AttendanceCorrection.status == status)
    return list(db.scalars(query.order_by(AttendanceCorrection.created_at.desc(), AttendanceCorrection.id.desc())))


def correction_data(item):
    return {"id": item.id, "attendance_record_id": item.attendance_record_id, "assigned_shift_id": item.record.assigned_shift_id,
        "student_id": item.record.student_id, "student_name": item.record.shift.student_name,
        "proposed_clock_in": item.proposed_clock_in, "proposed_clock_out": item.proposed_clock_out, "reason": item.reason,
        "status": item.status, "requested_by": item.requested_by, "created_at": item.created_at,
        "reviewed_by": item.reviewed_by, "reviewed_at": item.reviewed_at, "reviewer_note": item.reviewer_note}


def decide(db, supervisor, correction_id, data):
    reserve_write(db)
    item = db.scalar(select(AttendanceCorrection).join(AttendanceRecord).where(AttendanceCorrection.id == correction_id,
        AttendanceRecord.department_id == supervisor.department_id).execution_options(populate_existing=True))
    if item is None:
        raise HTTPException(404, "Attendance correction not found")
    if item.requested_by == supervisor.id:
        raise HTTPException(403, "You cannot review your own attendance correction")
    if item.status != "pending":
        raise HTTPException(409, "This correction has already been reviewed")
    record = item.record
    now = now_utc()
    before = snapshot(record)
    if data.status == "approved":
        if item.base_version != record.version:
            raise HTTPException(409, "Attendance changed after this request. Reject the stale request and ask for a new proposal.")
        validate_proposal(item.proposed_clock_in, item.proposed_clock_out, record.shift, department_zone(db, supervisor), now)
        no_overlap(db, record.student_id, item.proposed_clock_in, item.proposed_clock_out, record.id)
        record.clock_in_at = item.proposed_clock_in
        record.clock_out_at = item.proposed_clock_out
        record.status = "corrected"
        record.version += 1
        record.updated_at = now
    item.status = data.status
    item.reviewed_by = supervisor.id
    item.reviewed_at = now
    item.reviewer_note = data.reviewer_note
    audit(db, record, supervisor, "correction_" + data.status, now,
          {"correction_id": item.id, "before": before, "after": snapshot(record), "reviewer_note": data.reviewer_note})
    commit(db)
    return item


def record_data(record, timezone_name, settings, now):
    shift = record.shift
    start, _ = instants(shift, timezone_name)
    elapsed = max(0, ((record.clock_out_at or now) - record.clock_in_at).total_seconds()) if record.clock_in_at else 0
    return {"id": record.id, "student_id": record.student_id, "student_name": shift.student_name,
        "assigned_shift_id": shift.id, "schedule_run_id": shift.schedule_run_id, "schedule_status": shift.run.status,
        "department_id": record.department_id, "shift_date": shift.shift_date, "location_name": shift.location_name,
        "scheduled_start": start, "scheduled_end": instants(shift, timezone_name)[1], "scheduled_hours": shift.duration_minutes / 60,
        "clock_in_at": record.clock_in_at, "clock_out_at": record.clock_out_at, "status": record.status,
        "actual_hours": round(elapsed / 3600, 4), "late": bool(record.clock_in_at and record.clock_in_at > start + timedelta(minutes=settings.attendance_late_grace_minutes)),
        "created_at": record.created_at, "updated_at": record.updated_at, "version": record.version}


def report(db, user, settings, start_date=None, end_date=None, status=None, student_id=None):
    timezone_name = department_zone(db, user)
    tz = zone(timezone_name)
    now = now_utc()
    today = now.astimezone(tz).date()
    week_start = today - timedelta(days=today.weekday())
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "Filter start date must precede end date")
    selected_student = user.id if user.role == "student" else student_id
    records_query = select(AttendanceRecord).where(AttendanceRecord.department_id == user.department_id)
    shifts_query = select(AssignedShift).join(ScheduleRun).where(ScheduleRun.department_id == user.department_id,
                                                               ScheduleRun.status.in_(["published", "archived"]))
    if selected_student:
        records_query = records_query.where(AttendanceRecord.student_id == selected_student)
        shifts_query = shifts_query.where(AssignedShift.student_id == selected_student)
    all_records = list(db.scalars(records_query.order_by(AttendanceRecord.id.desc())))
    all_shifts = list(db.scalars(shifts_query.order_by(AssignedShift.shift_date, AssignedShift.start_time, AssignedShift.id)))
    record_map = {record.assigned_shift_id: record for record in all_records}
    records = [record for record in all_records if (not start_date or record.shift.shift_date >= start_date)
        and (not end_date or record.shift.shift_date <= end_date) and (not status or record.status == status)]
    shifts = []
    for shift in all_shifts:
        if (start_date and shift.shift_date < start_date) or (end_date and shift.shift_date > end_date):
            continue
        record = record_map.get(shift.id)
        if shift.run.status != "published" and record is None and user.role != "student":
            continue
        try:
            start, end = shift_instants(shift, timezone_name)
            opens = start - timedelta(minutes=settings.clock_in_early_minutes)
            closes = min(start + timedelta(minutes=settings.clock_in_late_minutes), end)
            eligible = shift.run.status == "published" and record is None and opens <= now <= closes and now < end
            missed = end <= now and (record is None or record.clock_in_at is None) and shift.run.status == "published"
            issue = None
        except ValueError as error:
            start = end = opens = closes = None; eligible = missed = False; issue = str(error)
        shifts.append({"id": shift.id, "student_id": shift.student_id, "student_name": shift.student_name,
            "location_name": shift.location_name, "shift_date": shift.shift_date, "schedule_status": shift.run.status,
            "scheduled_start": start, "scheduled_end": end, "scheduled_hours": shift.duration_minutes / 60,
            "clock_in_opens": opens, "clock_in_closes": closes, "can_clock_in": eligible,
            "missed": missed, "timing_issue": issue, "attendance_record_id": record.id if record else None})
    week_utc = local_to_utc(datetime.combine(week_start, time()), timezone_name)
    next_week = local_to_utc(datetime.combine(week_start + timedelta(days=7), time()), timezone_name)
    weekly_seconds = sum(max(0, (min(record.clock_out_at or now, next_week, now) - max(record.clock_in_at, week_utc)).total_seconds())
        for record in all_records if record.clock_in_at)
    rows = [record_data(record, timezone_name, settings, now) for record in records]
    active = [record_data(record, timezone_name, settings, now) for record in all_records if record.status == "active"]
    current = [shift for shift in shifts if shift["schedule_status"] == "published"]
    next_shift = next((shift for shift in current if shift["scheduled_end"] and shift["scheduled_end"] > now and shift["attendance_record_id"] is None), None)
    return {"timezone": timezone_name, "server_now": now, "records": rows, "active_records": active, "shifts": shifts,
        "today_shifts": [shift for shift in current if shift["shift_date"] == today], "next_shift": next_shift,
        "week_start": week_start, "actual_weekly_hours": round(weekly_seconds / 3600, 4),
        "total_actual_hours": round(sum(row["actual_hours"] for row in rows), 4),
        "scheduled_hours": sum(shift["scheduled_hours"] for shift in current),
        "late_count": sum(row["late"] for row in rows), "missed_count": sum(shift["missed"] for shift in current),
        "clock_in_early_minutes": settings.clock_in_early_minutes, "clock_in_late_minutes": settings.clock_in_late_minutes,
        "late_grace_minutes": settings.attendance_late_grace_minutes}


def csv_export(report_data):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Record ID", "Student", "Student ID", "Shift ID", "Shift date", "Location", "Schedule status",
                     "Scheduled hours", "Clock in UTC", "Clock out UTC", "Actual hours", "Status", "Late", "Department timezone"])
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
    for row in report_data["records"]:
        writer.writerow([row["id"], safe(row["student_name"]), row["student_id"], row["assigned_shift_id"], row["shift_date"],
            safe(row["location_name"]), row["schedule_status"], row["scheduled_hours"],
            row["clock_in_at"].isoformat() if row["clock_in_at"] else "", row["clock_out_at"].isoformat() if row["clock_out_at"] else "",
            row["actual_hours"], row["status"], row["late"], report_data["timezone"]])
    return output.getvalue()
