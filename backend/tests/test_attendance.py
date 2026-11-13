from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.core.attendance_time import UTC, local_to_utc, shift_instants
from app.core.config import BACKEND_DIR, Settings
from app.core.security import hasher
from app.models import (AssignedShift, AttendanceCorrection, AttendanceEvent, AttendanceRecord,
                        ScheduleRun, StaffingRequirement, WorkLocation)
from main import create_app
import test_phase2 as phase2
from database_support import concurrency_app

DAY = date(2026, 11, 16)
START = datetime(2026, 11, 16, 15, tzinfo=UTC)  # 09:00 CST


class AttendanceTests(unittest.TestCase):
    request = phase2.Phase2Tests.request
    headers = phase2.Phase2Tests.headers

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hasher.hash(phase2.PASSWORD)

    def setUp(self):
        phase2.Phase2Tests.setUp(self)
        with self.app.state.session_factory() as db:
            location = WorkLocation(department_id=1, name="Front Desk", description="Test", is_active=True)
            db.add(location); db.flush(); self.location_id = location.id
            requirement = StaffingRequirement(department_id=1, location_id=location.id, day_of_week=0,
                start_time=time(9), end_time=time(12), required_count=1, is_active=True)
            db.add(requirement); db.flush(); self.requirement_id = requirement.id
            db.commit()
        self.shift_id, self.run_id = self.make_shift()

    def make_shift(self, student_id=1, shift_date=DAY, start=time(9), end=time(12), status="published", run_id=None):
        with self.app.state.session_factory() as db:
            if run_id:
                run = db.get(ScheduleRun, run_id)
            else:
                run = ScheduleRun(department_id=1, week_start=shift_date - timedelta(days=shift_date.weekday()), status=status,
                    created_by=4, published_by=4 if status == "published" else None,
                    published_at=START - timedelta(days=1) if status == "published" else None,
                    algorithm_version="test", summary={"timezone": "America/Chicago"}, version=1)
                db.add(run); db.flush()
            shift = AssignedShift(schedule_run_id=run.id, student_id=student_id, location_id=self.location_id,
                requirement_id=self.requirement_id, shift_date=shift_date, start_time=start, end_time=end,
                duration_minutes=(end.hour * 60 + end.minute) - (start.hour * 60 + start.minute), status=status,
                student_name=f"Student {student_id}", location_name="Front Desk")
            db.add(shift); db.commit()
            return shift.id, run.id

    def clock_in(self, when=START, shift_id=None, student_id=1):
        with patch("app.services.attendance.now_utc", return_value=when):
            return self.request("POST", "/students/me/attendance/clock-in", user_id=student_id,
                                json={"assigned_shift_id": shift_id or self.shift_id})

    def clock_out(self, record_id, when):
        with patch("app.services.attendance.now_utc", return_value=when):
            return self.request("POST", f"/students/me/attendance/{record_id}/clock-out", json={})

    def correction(self, start=None, end=None, now=None, shift_id=None):
        with patch("app.services.attendance.now_utc", return_value=now or START + timedelta(hours=5)):
            return self.request("POST", "/students/me/attendance/corrections", json={"assigned_shift_id": shift_id or self.shift_id,
                "proposed_clock_in": start or "2026-11-16T09:00", "proposed_clock_out": end or "2026-11-16T12:00", "reason": "Forgot to record attendance"})

    def decide(self, correction_id, status="approved", user_id=4):
        with patch("app.services.attendance.now_utc", return_value=START + timedelta(hours=6)):
            return self.request("POST", f"/supervisor/attendance/corrections/{correction_id}/decision", user_id=user_id,
                                json={"status": status, "reviewer_note": "Checked shift attendance"})

    def test_valid_clock_in_out_utc_storage_and_weekly_totals(self):
        result = self.clock_in()
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(datetime.fromisoformat(result.json()["clock_in_at"].replace("Z", "+00:00")), START)
        record_id = result.json()["id"]
        out = self.clock_out(record_id, START + timedelta(hours=3))
        self.assertEqual(out.status_code, 200, out.text)
        self.assertEqual(out.json()["actual_hours"], 3)
        self.assertEqual(out.json()["status"], "completed")
        with self.app.state.engine.connect() as connection:
            stored = connection.exec_driver_sql("SELECT clock_in_at FROM attendance_records").scalar()
            self.assertTrue(stored.endswith("Z"))
        with patch("app.services.attendance.now_utc", return_value=START + timedelta(hours=4)):
            report = self.request("GET", "/students/me/attendance").json()
        self.assertEqual(report["actual_weekly_hours"], 3)
        self.assertEqual(report["scheduled_hours"], 3)

    def test_published_ownership_roles_and_forged_times(self):
        self.assertEqual(self.clock_in(student_id=2).status_code, 404)
        with self.app.state.session_factory() as db:
            db.get(ScheduleRun, self.run_id).status = "draft"; db.commit()
        self.assertEqual(self.clock_in().status_code, 404)
        self.assertEqual(self.request("POST", "/students/me/attendance/clock-in", user_id=4, json={"assigned_shift_id": self.shift_id}).status_code, 403)
        self.assertEqual(self.request("POST", "/students/me/attendance/clock-in", json={"assigned_shift_id": self.shift_id, "clock_in_at": START.isoformat()}).status_code, 422)
        self.assertEqual(self.client.get("/api/students/me/attendance").status_code, 401)

    def test_early_late_and_end_boundaries(self):
        self.assertEqual(self.clock_in(START - timedelta(minutes=16)).status_code, 422)
        self.assertEqual(self.clock_in(START + timedelta(minutes=31)).status_code, 422)
        self.assertEqual(self.clock_in(START + timedelta(hours=3)).status_code, 422)
        self.assertEqual(self.clock_in(START - timedelta(minutes=15)).status_code, 201)

    def test_duplicate_and_multiple_active_clock_ins(self):
        result = self.clock_in()
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.clock_in().status_code, 409)
        other, _ = self.make_shift(run_id=self.run_id)
        self.assertEqual(self.clock_in(shift_id=other).status_code, 409)
        self.clock_out(result.json()["id"], START + timedelta(hours=1))
        self.assertEqual(self.clock_in(START + timedelta(hours=1)).status_code, 409)

    def test_clock_out_requires_own_active_record(self):
        self.assertEqual(self.clock_out(999, START).status_code, 404)
        record_id = self.clock_in().json()["id"]
        self.assertEqual(self.request("POST", f"/students/me/attendance/{record_id}/clock-out", user_id=2, json={}).status_code, 404)
        self.assertEqual(self.clock_out(record_id, START + timedelta(hours=1)).status_code, 200)
        self.assertEqual(self.clock_out(record_id, START + timedelta(hours=2)).status_code, 409)

    def test_correction_for_missing_clock_in_and_approval_audit(self):
        requested = self.correction()
        self.assertEqual(requested.status_code, 201, requested.text)
        item = requested.json()
        self.assertEqual(self.correction().status_code, 409)
        approved = self.decide(item["id"])
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["reviewed_by"], 4)
        record_id = item["attendance_record_id"]
        audit = self.request("GET", f"/supervisor/attendance/{record_id}/audit", user_id=4).json()
        self.assertIsNone(audit[0]["details"]["original"]["clock_in_at"])
        self.assertEqual(audit[-1]["action"], "correction_approved")
        with self.app.state.session_factory() as db:
            record = db.get(AttendanceRecord, record_id)
            self.assertEqual(record.status, "corrected")
            self.assertEqual(record.clock_in_at, START)

    def test_completed_record_originals_retained_on_correction(self):
        record = self.clock_in(START + timedelta(minutes=10)).json()
        self.clock_out(record["id"], START + timedelta(hours=2))
        item = self.correction().json()
        self.assertEqual(self.decide(item["id"]).status_code, 200)
        audit = self.request("GET", f"/students/me/attendance/{record['id']}/audit").json()
        self.assertIn("15:10:00", audit[-1]["details"]["before"]["clock_in_at"])
        self.assertIn("15:00:00", audit[-1]["details"]["after"]["clock_in_at"])
        self.assertEqual(self.decide(item["id"]).status_code, 409)

    def test_rejection_does_not_change_actual_times(self):
        item = self.correction().json()
        self.assertEqual(self.decide(item["id"], "rejected").status_code, 200)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(AttendanceRecord, item["attendance_record_id"]).status, "missing")
            self.assertIsNone(db.get(AttendanceRecord, item["attendance_record_id"]).clock_in_at)

    def test_forgot_clock_out_and_stale_proposal(self):
        record_id = self.clock_in().json()["id"]
        item = self.correction().json()
        self.clock_out(record_id, START + timedelta(hours=4))
        self.assertEqual(self.decide(item["id"]).status_code, 409)
        self.assertEqual(self.decide(item["id"], "rejected").status_code, 200)

    def test_forgot_clock_out_approval_closes_active_record(self):
        record_id = self.clock_in().json()["id"]
        item = self.correction().json()
        self.assertEqual(self.decide(item["id"]).status_code, 200)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(AttendanceRecord, record_id).status, "corrected")

    def test_correction_invalid_future_dates_and_intervals(self):
        self.assertEqual(self.correction(end="2026-11-16T08:00").status_code, 422)
        self.assertEqual(self.correction(end="2026-11-17T12:00").status_code, 422)
        self.assertEqual(self.correction(start="2026-11-15T09:00", end="2026-11-15T12:00").status_code, 422)
        self.assertEqual(self.correction(now=START + timedelta(hours=1), end="2026-11-16T09:30").status_code, 422)

    def test_correction_overlap_rejected_on_request_and_review(self):
        first = self.clock_in().json()["id"]
        self.clock_out(first, START + timedelta(hours=1))
        proposal = self.correction(end="2026-11-16T10:30").json()
        second_shift, _ = self.make_shift(start=time(10), end=time(12), run_id=self.run_id)
        second = self.clock_in(START + timedelta(hours=1), second_shift)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(self.decide(proposal["id"]).status_code, 409)
        self.clock_out(second.json()["id"], START + timedelta(hours=2))
        self.assertEqual(self.correction(shift_id=second_shift, start="2026-11-16T09:30", end="2026-11-16T11:00").status_code, 409)

    def test_department_permissions_csv_and_private_history(self):
        record = self.clock_in().json()
        item = self.correction().json()
        self.assertEqual(self.decide(item["id"], user_id=1).status_code, 403)
        self.assertEqual(self.decide(item["id"], user_id=5).status_code, 404)
        self.assertEqual(self.request("GET", "/supervisor/attendance", user_id=5).json()["records"], [])
        self.assertEqual(self.request("GET", "/students/me/attendance", user_id=2).json()["records"], [])
        for path in ("/supervisor/attendance/export.csv", "/supervisor/attendance/corrections"):
            self.assertEqual(self.request("GET", path).status_code, 403)
        self.assertEqual(self.request("GET", f"/supervisor/attendance/{record['id']}/audit", user_id=5).status_code, 404)
        self.assertEqual(self.request("GET", f"/students/me/attendance/{record['id']}/audit", user_id=2).status_code, 404)
        exported = self.request("GET", "/supervisor/attendance/export.csv", user_id=4)
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported.headers["content-type"])
        self.assertIn("Student 1", exported.text)
        self.assertNotIn("Student 1", self.request("GET", "/supervisor/attendance/export.csv", user_id=5).text)

    def test_report_late_missed_and_filters(self):
        self.clock_in(START + timedelta(minutes=6))
        self.make_shift(student_id=2, run_id=self.run_id)
        with patch("app.services.attendance.now_utc", return_value=START + timedelta(hours=5)):
            result = self.request("GET", "/supervisor/attendance?start_date=2026-11-16&end_date=2026-11-16", user_id=4).json()
            self.assertEqual(result["late_count"], 1)
            self.assertEqual(result["missed_count"], 1)
            self.assertEqual(len(result["active_records"]), 1)
            self.assertEqual(self.request("GET", "/supervisor/attendance?student_id=2", user_id=4).json()["records"], [])
            self.assertEqual(self.request("GET", "/supervisor/attendance?status=completed", user_id=4).json()["records"], [])

    def test_schedule_replacement_retains_original_shift_and_clock_out(self):
        record = self.clock_in().json()
        generated = self.request("POST", "/supervisor/schedules", user_id=4, json={"week_start": "2026-11-16"}).json()
        published = self.request("POST", f"/supervisor/schedules/{generated['id']}/publish", user_id=4,
            json={"expected_version": generated["version"], "acknowledge_uncovered": True, "expected_current_published_id": self.run_id})
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(self.clock_out(record["id"], START + timedelta(hours=1)).status_code, 200)
        with self.app.state.session_factory() as db:
            original = db.get(AttendanceRecord, record["id"])
            self.assertEqual(original.assigned_shift_id, self.shift_id)
            self.assertEqual(original.shift.run.status, "archived")

    def test_failure_rolls_back_clock_in_and_correction(self):
        with patch("app.services.attendance.audit", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.clock_in()
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AttendanceRecord)), 0)
        item = self.correction().json()
        with patch("app.services.attendance.audit", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.decide(item["id"])
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(AttendanceCorrection, item["id"]).status, "pending")
            self.assertEqual(db.get(AttendanceRecord, item["attendance_record_id"]).status, "missing")

    def test_unique_active_constraint_and_concurrent_clock_ins(self):
        second_shift, _ = self.make_shift(run_id=self.run_id)
        with concurrency_app(self.app, self.settings) as app:
            with TestClient(app) as client, patch("app.services.attendance.now_utc", return_value=START):
                def clock(shift_id):
                    return client.post("/api/students/me/attendance/clock-in", headers=self.headers(), json={"assigned_shift_id": shift_id}).status_code
                with ThreadPoolExecutor(max_workers=2) as pool:
                    statuses = list(pool.map(clock, [self.shift_id, second_shift]))
                self.assertEqual(sorted(statuses), [201, 409])
                with app.state.session_factory() as db:
                    existing = db.scalar(select(AttendanceRecord))
                    other = second_shift if existing.assigned_shift_id == self.shift_id else self.shift_id
                    db.add(AttendanceRecord(student_id=1, assigned_shift_id=other, department_id=1, clock_in_at=START,
                        status="active", created_at=START, updated_at=START, version=1))
                    with self.assertRaises(IntegrityError):
                        db.commit()
                    db.rollback()

    def test_clock_out_after_midnight(self):
        with self.app.state.session_factory() as db:
            shift = db.get(AssignedShift, self.shift_id)
            shift.start_time = time(23); shift.end_time = time(23, 30); shift.duration_minutes = 30
            db.commit()
        start = datetime(2026, 11, 17, 5, tzinfo=UTC)
        record = self.clock_in(start).json()
        result = self.clock_out(record["id"], start + timedelta(hours=2))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["actual_hours"], 2)

    def test_actual_elapsed_hours_differ_from_scheduled_hours_at_fall_back(self):
        shift_id, _ = self.make_shift(shift_date=date(2026, 11, 1), start=time(0, 30), end=time(2, 30))
        start = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
        record = self.clock_in(start, shift_id).json()
        result = self.clock_out(record["id"], start + timedelta(hours=3))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["scheduled_hours"], 2)
        self.assertEqual(result.json()["actual_hours"], 3)

    def test_actual_weekly_hours_clip_at_department_midnight(self):
        shift_id, _ = self.make_shift(shift_date=date(2026, 11, 15), start=time(23), end=time(23, 30))
        start = datetime(2026, 11, 16, 5, tzinfo=UTC)  # Sunday 23:00 CST
        record = self.clock_in(start, shift_id).json()
        self.clock_out(record["id"], start + timedelta(hours=3))
        with patch("app.services.attendance.now_utc", return_value=start + timedelta(hours=4)):
            report = self.request("GET", "/students/me/attendance").json()
        self.assertEqual(report["actual_weekly_hours"], 2)
        self.assertEqual(report["total_actual_hours"], 3)

    def test_correction_can_select_second_repeated_local_hour(self):
        shift_id, _ = self.make_shift(shift_date=date(2026, 11, 1), start=time(1), end=time(2))
        with patch("app.services.attendance.now_utc", return_value=START):
            response = self.request("POST", "/students/me/attendance/corrections", json={"assigned_shift_id": shift_id,
                "proposed_clock_in": "2026-11-01T01:30", "proposed_clock_out": "2026-11-01T01:45",
                "clock_in_fold": 1, "clock_out_fold": 1, "reason": "Worked the second repeated hour"})
        self.assertEqual(response.status_code, 201, response.text)
        value = datetime.fromisoformat(response.json()["proposed_clock_in"].replace("Z", "+00:00"))
        self.assertEqual(value, datetime(2026, 11, 1, 7, 30, tzinfo=UTC))

    def test_csv_neutralizes_spreadsheet_formulas(self):
        self.clock_in()
        with self.app.state.session_factory() as db:
            db.get(AssignedShift, self.shift_id).student_name = "=SUM(1,2)"; db.commit()
        exported = self.request("GET", "/supervisor/attendance/export.csv", user_id=4)
        self.assertIn("'=SUM", exported.text)

    def test_early_clock_in_before_midnight_can_be_corrected(self):
        with self.app.state.session_factory() as db:
            shift = db.get(AssignedShift, self.shift_id)
            shift.start_time = time(0); shift.end_time = time(1); shift.duration_minutes = 60
            db.commit()
        start = datetime(2026, 11, 16, 5, 50, tzinfo=UTC)  # Previous local date, 23:50
        response = self.clock_in(start)
        self.assertEqual(response.status_code, 201, response.text)
        self.clock_out(response.json()["id"], datetime(2026, 11, 16, 6, 45, tzinfo=UTC))
        correction = self.correction(start="2026-11-15T23:55", end="2026-11-16T00:45")
        self.assertEqual(correction.status_code, 201, correction.text)
        self.assertEqual(self.decide(correction.json()["id"]).status_code, 200)


class AttendanceTimezoneTests(unittest.TestCase):
    def test_chicago_conversion_and_ambiguous_folds(self):
        self.assertEqual(local_to_utc(datetime(2026, 11, 16, 9), "America/Chicago"), START)
        first = local_to_utc(datetime(2026, 11, 1, 1, 30), "America/Chicago", 0)
        second = local_to_utc(datetime(2026, 11, 1, 1, 30), "America/Chicago", 1)
        self.assertEqual(second - first, timedelta(hours=1))

    def test_nonexistent_spring_time_rejected(self):
        with self.assertRaises(ValueError):
            local_to_utc(datetime(2026, 3, 8, 2, 30), "America/Chicago")

    def test_shift_elapsed_time_across_dst_boundaries(self):
        class Shift:
            shift_date = date(2026, 11, 1)
            start_time = time(0, 30)
            end_time = time(2, 30)
        start, end = shift_instants(Shift, "America/Chicago")
        self.assertEqual(end - start, timedelta(hours=3))
        Shift.shift_date = date(2026, 3, 8)
        Shift.start_time = time(1, 30); Shift.end_time = time(3, 30)
        start, end = shift_instants(Shift, "America/Chicago")
        self.assertEqual(end - start, timedelta(hours=1))


if __name__ == "__main__":
    unittest.main()
