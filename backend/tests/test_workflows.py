"""Phase 4 leave, manual-edit, publication and atomicity regression contracts."""
from datetime import date, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.core.security import hasher
from app.core.config import BACKEND_DIR, Settings
from fastapi.testclient import TestClient
from main import create_app
from app.models import (ClassSchedule, LocationEligibility, ScheduleEvent, ScheduleRun,
                        TimeOffRequest, User)
import test_phase2 as phase2
import test_scheduling as phase3
from database_support import concurrency_app


class WorkflowTests(unittest.TestCase):
    setUp_base = phase2.Phase2Tests.setUp
    request = phase2.Phase2Tests.request
    headers = phase2.Phase2Tests.headers
    add_location = phase3.SchedulingApiTests.add_location
    demand = phase3.SchedulingApiTests.demand
    generate = phase3.SchedulingApiTests.generate

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hasher.hash(phase2.PASSWORD)

    def setUp(self):
        self.setUp_base()
        self.location_id = self.add_location()["id"]
        for student_id in (1, 2):
            response = self.request("POST", "/students/me/availability", user_id=student_id,
                json={"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"})
            self.assertEqual(response.status_code, 201)
        response = self.request("POST", "/supervisor/requirements", user_id=4, json=self.demand(self.location_id))
        self.requirement_id = response.json()["id"]

    def leave(self, student_id=1, **changes):
        response = self.request("POST", "/students/me/time-off", user_id=student_id,
            json={"start_date": "2026-10-19", "end_date": "2026-10-19", **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def decide(self, request_id, status="approved", user_id=4):
        return self.request("POST", f"/supervisor/time-off/{request_id}/decision", user_id=user_id,
                            json={"status": status, "decision_note": "Reviewed by supervisor"})

    def get_run(self, run_id):
        return self.request("GET", f"/supervisor/schedules/{run_id}", user_id=4).json()

    def publish(self, run, **changes):
        return self.request("POST", f"/supervisor/schedules/{run['id']}/publish", user_id=4,
            json={"expected_version": run["version"], "acknowledge_uncovered": True, **changes})

    def reassign(self, run, shift, student_id, **changes):
        return self.request("PATCH", f"/supervisor/schedules/{run['id']}/shifts/{shift['id']}", user_id=4,
                            json={"expected_version": run["version"], "student_id": student_id, **changes})

    def remove(self, run, shift):
        return self.request("POST", f"/supervisor/schedules/{run['id']}/shifts/{shift['id']}/remove", user_id=4,
                            json={"expected_version": run["version"]})

    def add_body(self, run, shift, student_id):
        return {"expected_version": run["version"], "student_id": student_id,
                "requirement_id": shift["requirement_id"], "shift_date": shift["shift_date"],
                "start_time": shift["start_time"], "end_time": shift["end_time"]}

    def test_request_lifecycle_filters_and_audit_times(self):
        leave = self.leave(reason="Family visit", end_date="2026-10-21")
        self.assertEqual(leave["status"], "pending")
        self.assertTrue(leave["created_at"].endswith("Z"))
        response = self.decide(leave["id"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["reviewer_id"], 4)
        self.assertTrue(response.json()["reviewed_at"].endswith("Z"))
        self.assertEqual(len(self.request("GET", "/supervisor/time-off?status=approved&start_date=2026-10-21&end_date=2026-10-21", user_id=4).json()), 1)
        self.assertEqual(self.request("GET", "/supervisor/time-off?status=pending", user_id=4).json(), [])
        self.assertEqual(self.request("GET", "/supervisor/time-off?start_date=2026-10-22", user_id=4).json(), [])
        self.assertEqual(self.decide(leave["id"], "rejected").status_code, 409)
        self.assertEqual(self.request("POST", f"/students/me/time-off/{leave['id']}/cancel").status_code, 409)

    def test_leave_validation_cancellation_and_ownership(self):
        self.assertEqual(self.request("POST", "/students/me/time-off", json={"start_date": "2026-10-20", "end_date": "2026-10-19"}).status_code, 422)
        leave = self.leave()
        for path in [f"/students/me/time-off/{leave['id']}", f"/students/me/time-off/{leave['id']}/cancel"]:
            self.assertEqual(self.request("GET" if not path.endswith("cancel") else "POST", path, user_id=2).status_code, 404)
        self.assertEqual(self.request("GET", "/students/me/time-off", user_id=2).json(), [])
        cancelled = self.request("POST", f"/students/me/time-off/{leave['id']}/cancel")
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertTrue(cancelled.json()["cancelled_at"].endswith("Z"))
        self.assertEqual(self.decide(leave["id"]).status_code, 409)

    def test_permissions_and_department_isolation(self):
        leave = self.leave()
        self.assertEqual(self.decide(leave["id"], user_id=1).status_code, 403)
        self.assertEqual(self.decide(leave["id"], user_id=5).status_code, 404)
        self.assertEqual(self.request("GET", "/supervisor/time-off", user_id=5).json(), [])
        run = self.generate()
        shift = run["shifts"][0]
        for path, body in [(f"/supervisor/schedules/{run['id']}/publish", {"expected_version": 1}),
                           (f"/supervisor/schedules/{run['id']}/shifts/{shift['id']}/remove", {"expected_version": 1})]:
            self.assertEqual(self.request("POST", path, user_id=1, json=body).status_code, 403)
            self.assertEqual(self.request("POST", path, user_id=5, json=body).status_code, 404)
        for suffix in ("validation", "events"):
            self.assertEqual(self.request("GET", f"/supervisor/schedules/{run['id']}/{suffix}", user_id=5).status_code, 404)

    def test_only_approved_leave_blocks_engine_inclusively(self):
        first = self.leave(1, start_date="2026-10-18", end_date="2026-10-19")
        self.assertTrue(any(s["student_id"] == 1 for s in self.generate()["shifts"]))
        self.decide(first["id"])
        self.assertTrue(all(s["student_id"] != 1 for s in self.generate()["shifts"]))
        rejected = self.leave(2)
        self.decide(rejected["id"], "rejected")
        self.assertTrue(any(s["student_id"] == 2 for s in self.generate()["shifts"]))
        cancelled = self.leave(2)
        self.request("POST", f"/students/me/time-off/{cancelled['id']}/cancel", user_id=2)
        self.assertTrue(any(s["student_id"] == 2 for s in self.generate()["shifts"]))

    def test_late_approval_notifies_without_changing_draft_or_published(self):
        run = self.generate()
        student_id = run["shifts"][0]["student_id"]
        leave = self.leave(student_id)
        published = self.publish(run).json()
        self.decide(leave["id"])
        self.assertEqual(self.get_run(run["id"]), published)
        warnings = self.request("GET", "/supervisor/schedule-conflicts", user_id=4).json()
        self.assertTrue(any(w["run_id"] == run["id"] and w["run_status"] == "published" for w in warnings))
        self.assertEqual(self.request("GET", "/supervisor/schedule-conflicts", user_id=5).json(), [])
        new = self.generate()
        self.assertTrue(all(s["student_id"] != student_id for s in new["shifts"]))

    def test_valid_reassignment_updates_metrics_audit_and_version(self):
        run = self.generate()
        shift = run["shifts"][0]
        target = 3 - shift["student_id"]
        result = self.reassign(run, shift, target)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["version"], 2)
        self.assertEqual(result.json()["summary"]["total_assigned_hours"], 3)
        self.assertEqual(next(s["student_id"] for s in result.json()["shifts"] if s["id"] == shift["id"]), target)
        self.assertEqual(self.reassign(run, shift, target).status_code, 409)
        self.assertEqual(self.request("GET", f"/supervisor/schedules/{run['id']}/events", user_id=4).json()[0]["action"], "reassign")

    def assert_bad_reassignment(self, mutate, expected_text):
        run = self.generate(); shift = run["shifts"][0]; target = 3 - shift["student_id"]
        mutate(target, shift)
        response = self.reassign(run, shift, target)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn(expected_text, response.json()["detail"])
        self.assertEqual(self.get_run(run["id"]), run)

    def test_class_conflict_rejected_without_mutation(self):
        def add_class(target, shift):
            with self.app.state.session_factory() as db:
                db.add(ClassSchedule(student_id=target, course_name="Conflict", day_of_week=0,
                    start_time=time.fromisoformat(shift["start_time"]), end_time=time.fromisoformat(shift["end_time"])))
                db.commit()
        self.assert_bad_reassignment(add_class, "class")

    def test_unavailable_and_hour_limit_and_eligibility_rejected(self):
        def zero_hours(target, shift):
            with self.app.state.session_factory() as db:
                db.get(User, target).max_weekly_hours = 0; db.commit()
        self.assert_bad_reassignment(zero_hours, "maximum weekly hours")

    def test_unavailable_rejected(self):
        def no_availability(target, shift):
            with self.app.state.session_factory() as db:
                student = db.get(User, target)
                student.availability.clear(); db.commit()
        self.assert_bad_reassignment(no_availability, "availability")

    def test_ineligible_and_cross_department_rejected(self):
        run = self.generate(); shift = run["shifts"][0]; target = 3 - shift["student_id"]
        with self.app.state.session_factory() as db:
            db.delete(db.get(LocationEligibility, (self.location_id, target))); db.commit()
        self.assertEqual(self.reassign(run, shift, target).status_code, 422)
        self.assertEqual(self.reassign(run, shift, 3).status_code, 422)
        self.assertEqual(self.get_run(run["id"]), run)

    def test_time_off_reassignment_and_publish_rejected(self):
        run = self.generate(); shift = run["shifts"][0]; target = 3 - shift["student_id"]
        self.decide(self.leave(target)["id"])
        self.assertEqual(self.reassign(run, shift, target).status_code, 422)
        # Another assignment for target already exists; publication must revalidate it.
        self.assertEqual(self.publish(run).status_code, 422)

    def test_remove_refill_capacity_and_atomic_failure(self):
        run = self.generate(); shift = run["shifts"][0]
        body = self.add_body(run, shift, 3 - shift["student_id"])
        full = self.request("POST", f"/supervisor/schedules/{run['id']}/shifts", user_id=4, json=body)
        self.assertEqual(full.status_code, 409, full.text)
        self.assertEqual(self.get_run(run["id"]), run)
        removed = self.remove(run, shift).json()
        self.assertGreater(removed["summary"]["unfilled_staff_minutes"], 0)
        body = self.add_body(removed, shift, shift["student_id"])
        filled = self.request("POST", f"/supervisor/schedules/{run['id']}/shifts", user_id=4, json=body)
        self.assertEqual(filled.status_code, 201, filled.text)
        self.assertEqual(filled.json()["summary"]["coverage_percent"], 100)
        snapshot = filled.json()
        with patch("app.services.schedule_editor.recompute", side_effect=RuntimeError("simulated save failure")):
            with self.assertRaises(RuntimeError):
                self.remove(snapshot, snapshot["shifts"][0])
        self.assertEqual(self.get_run(run["id"]), snapshot)

    def test_double_booking_rejected(self):
        second_location = self.add_location("Second")["id"]
        self.request("POST", "/supervisor/requirements", user_id=4, json=self.demand(second_location))
        run = self.generate(); shift = run["shifts"][0]
        other = next(s for s in run["shifts"] if s["location_id"] != shift["location_id"] and s["start_time"] < shift["end_time"] and shift["start_time"] < s["end_time"])
        self.assertEqual(self.reassign(run, shift, other["student_id"]).status_code, 422)

    def test_publication_visibility_read_only_history_and_stale_publish(self):
        first = self.generate()
        self.assertIsNone(self.request("GET", "/students/me/schedule").json()["run_id"])
        published = self.publish(first)
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["status"], "published")
        self.assertTrue(published.json()["published_at"].endswith("Z"))
        self.assertEqual(self.remove(published.json(), published.json()["shifts"][0]).status_code, 409)
        self.assertEqual(self.request("GET", "/students/me/schedule").json()["run_id"], first["id"])
        second = self.generate()
        self.assertEqual(self.request("GET", "/students/me/schedule").json()["run_id"], first["id"])
        self.assertEqual(self.publish(second).status_code, 409)
        response = self.publish(second, expected_current_published_id=first["id"])
        self.assertEqual(response.status_code, 200, response.text)
        previous = self.get_run(first["id"])
        self.assertEqual(previous["status"], "archived")
        self.assertEqual(len(previous["shifts"]), len(first["shifts"]))
        self.assertTrue(all(s["status"] == "archived" for s in previous["shifts"]))
        self.assertEqual(self.request("GET", "/students/me/schedule").json()["run_id"], second["id"])
        self.assertIsNone(self.request("GET", "/students/me/schedule", user_id=3).json()["run_id"])
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ScheduleRun).where(ScheduleRun.status == "published")), 1)

    def test_incomplete_requires_acknowledgement(self):
        run = self.generate(); removed = self.remove(run, run["shifts"][0]).json()
        self.assertEqual(self.publish(removed, acknowledge_uncovered=False).status_code, 409)
        self.assertEqual(self.get_run(run["id"])["status"], "draft")
        self.assertEqual(self.publish(removed).status_code, 200)

    def test_changed_staffing_requires_new_generation(self):
        run = self.generate()
        self.request("PUT", f"/supervisor/requirements/{self.requirement_id}", user_id=4,
                     json=self.demand(self.location_id, required_count=2))
        response = self.publish(run)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Staffing demand changed", response.json()["detail"])
        self.assertEqual(self.get_run(run["id"]), run)

    def test_partial_unique_index_and_publish_failure_rollback(self):
        first = self.generate(); second = self.generate()
        self.publish(first)
        with self.app.state.session_factory() as db:
            db.get(ScheduleRun, second["id"]).status = "published"
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
        with patch("app.services.schedule_editor.event", side_effect=RuntimeError("audit write failure")):
            with self.assertRaises(RuntimeError):
                self.publish(second, expected_current_published_id=first["id"])
        self.assertEqual(self.get_run(first["id"])["status"], "published")
        self.assertEqual(self.get_run(second["id"])["status"], "draft")

    def test_simultaneous_edits_accept_only_one_revision(self):
        run = self.generate(); shift = run["shifts"][0]
        with concurrency_app(self.app, self.settings) as app:
            with TestClient(app) as client:
                def remove():
                    return client.post(f"/api/supervisor/schedules/{run['id']}/shifts/{shift['id']}/remove",
                        headers=self.headers(4), json={"expected_version": run["version"]}).status_code
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: remove(), range(2)))
                self.assertEqual(sorted(results), [200, 409])
                updated = client.get(f"/api/supervisor/schedules/{run['id']}", headers=self.headers(4)).json()
                self.assertEqual(updated["version"], 2)


if __name__ == "__main__":
    unittest.main()
