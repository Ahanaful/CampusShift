from datetime import date, time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from app.core.config import BACKEND_DIR
from app.core.security import hasher
from app.db.session import create_session_factory
from app.models import (AssignedShift, Availability, ClassSchedule, Department,
                        LocationEligibility, ScheduleRun, StaffingRequirement, User, WorkLocation)
import test_phase2 as phase2


class SchedulingApiTests(unittest.TestCase):
    setUp = phase2.Phase2Tests.setUp
    request = phase2.Phase2Tests.request
    headers = phase2.Phase2Tests.headers

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hasher.hash(phase2.PASSWORD)

    def add_location(self, name="Front Desk", eligible=None):
        result = self.request("POST", "/supervisor/locations", user_id=4,
                              json={"name": name, "eligible_student_ids": [1, 2] if eligible is None else eligible})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def demand(self, location_id, **changes):
        return {"location_id": location_id, "day_of_week": 0, "start_time": "09:00", "end_time": "12:00", "required_count": 1, **changes}

    def test_location_eligibility_crud_and_department_scope(self):
        item = self.add_location()
        self.assertEqual(len(self.request("GET", "/students/me/locations").json()), 1)
        self.assertEqual(self.request("GET", "/students/me/locations", user_id=3).json(), [])
        self.assertEqual(self.request("GET", "/supervisor/locations", user_id=5).json(), [])
        self.assertEqual(self.request("GET", f"/supervisor/locations/{item['id']}", user_id=5).status_code, 404)
        self.assertEqual(self.request("PUT", f"/supervisor/locations/{item['id']}", user_id=5, json={"name": "Stolen"}).status_code, 404)
        self.assertEqual(self.request("POST", "/supervisor/locations", user_id=4, json={"name": "Invalid", "eligible_student_ids": [3]}).status_code, 422)
        self.assertEqual(self.request("POST", "/supervisor/locations", user_id=4, json={"name": "Invalid", "eligible_student_ids": [4]}).status_code, 422)
        response = self.request("PUT", f"/supervisor/locations/{item['id']}", user_id=4,
                                json={"name": "Updated", "is_active": False, "eligible_student_ids": [2]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["eligible_student_ids"], [2])
        self.assertEqual(self.request("GET", "/students/me/locations").json(), [])

    def test_requirement_crud_overlap_reactivation_and_validation(self):
        location = self.add_location()["id"]
        response = self.request("POST", "/supervisor/requirements", user_id=4, json=self.demand(location))
        self.assertEqual(response.status_code, 201, response.text)
        requirement_id = response.json()["id"]
        self.assertEqual(self.request("GET", f"/supervisor/requirements/{requirement_id}", user_id=4).status_code, 200)
        self.assertEqual(self.request("GET", f"/supervisor/requirements/{requirement_id}", user_id=5).status_code, 404)
        self.assertEqual(self.request("POST", "/supervisor/requirements", user_id=4, json=self.demand(location)).status_code, 409)
        for changes in [{"start_time": "23:00", "end_time": "01:00"}, {"end_time": "09:00"}, {"start_time": "09:15"},
                        {"required_count": 0}, {"required_count": 51}, {"day_of_week": 7}, {"department_id": 2}]:
            self.assertEqual(self.request("POST", "/supervisor/requirements", user_id=4, json=self.demand(location, **changes)).status_code, 422)
        self.assertEqual(self.request("PUT", f"/supervisor/requirements/{requirement_id}", user_id=5, json=self.demand(location)).status_code, 404)
        self.assertEqual(self.request("POST", "/supervisor/requirements", user_id=5, json=self.demand(location)).status_code, 404)
        self.assertEqual(self.request("PUT", f"/supervisor/requirements/{requirement_id}", user_id=4, json=self.demand(location, is_active=False)).status_code, 200)
        other = self.request("POST", "/supervisor/requirements", user_id=4, json=self.demand(location)).json()["id"]
        self.assertEqual(self.request("PUT", f"/supervisor/requirements/{requirement_id}", user_id=4, json=self.demand(location)).status_code, 409)
        self.assertEqual(self.request("DELETE", f"/supervisor/requirements/{other}", user_id=5).status_code, 404)
        self.assertEqual(self.request("DELETE", f"/supervisor/requirements/{other}", user_id=4).status_code, 204)
        self.assertEqual(len(self.request("GET", "/supervisor/requirements", user_id=4).json()), 1)

    def scenario(self):
        first = self.add_location("Front Desk")["id"]
        second = self.add_location("Study Help")["id"]
        with self.app.state.session_factory() as db:
            db.get(User, 1).max_weekly_hours = 5
            db.get(User, 2).max_weekly_hours = 6
            db.add_all([User(id=6, full_name="Zero Hours", email="zero@example.com", password_hash=self.password_hash,
                             role="student", department_id=1, max_weekly_hours=0),
                        User(id=7, full_name="Inactive", email="inactive@example.com", password_hash=self.password_hash,
                             role="student", department_id=1, max_weekly_hours=20, is_active=False)])
            db.flush()
            for student_id in [1, 2, 6, 7]:
                for day in range(7):
                    db.add(Availability(student_id=student_id, day_of_week=day, start_time=time(9), end_time=time(17)))
            db.add_all([ClassSchedule(student_id=1, course_name="Cloud", day_of_week=0, start_time=time(9), end_time=time(10)),
                        ClassSchedule(student_id=2, course_name="Networks", day_of_week=0, start_time=time(12), end_time=time(13))])
            for location_id in [first, second]:
                db.add_all([LocationEligibility(location_id=location_id, student_id=6), LocationEligibility(location_id=location_id, student_id=7)])
            db.commit()
        for location_id, day, count in [(first, 0, 2), (second, 0, 1), (first, 1, 1), (second, 6, 1)]:
            response = self.request("POST", "/supervisor/requirements", user_id=4,
                                    json=self.demand(location_id, day_of_week=day, end_time="17:00", required_count=count))
            self.assertEqual(response.status_code, 201, response.text)

    def generate(self):
        response = self.request("POST", "/supervisor/schedules", user_id=4, json={"week_start": "2026-10-19"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_realistic_week_all_hard_constraints_and_metrics(self):
        self.scenario()
        run = self.generate()
        self.assertGreater(len(run["shifts"]), 0)
        self.assertGreater(len(run["unfilled"]), 0)
        self.assertEqual(run["status"], "draft")
        totals = {}
        seen = set()
        with self.app.state.session_factory() as db:
            for shift in run["shifts"]:
                student = db.get(User, shift["student_id"])
                requirement = db.get(StaffingRequirement, shift["requirement_id"])
                day = date.fromisoformat(shift["shift_date"]).weekday()
                start = time.fromisoformat(shift["start_time"])
                end = time.fromisoformat(shift["end_time"])
                self.assertEqual(student.department_id, 1)
                self.assertTrue(student.is_active)
                self.assertIsNotNone(db.get(LocationEligibility, (shift["location_id"], student.id)))
                self.assertTrue(any(w.day_of_week == day and w.start_time <= start and end <= w.end_time for w in student.availability))
                self.assertFalse(any(w.day_of_week == day and w.start_time < end and start < w.end_time for w in student.classes))
                self.assertLess(start, end)
                self.assertEqual(requirement.day_of_week, day)
                self.assertLessEqual(requirement.start_time, start)
                self.assertLessEqual(end, requirement.end_time)
                expected_minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
                self.assertEqual(shift["duration_minutes"], expected_minutes)
                totals[student.id] = totals.get(student.id, 0) + expected_minutes
                self.assertLessEqual(totals[student.id], student.max_weekly_hours * 60)
                key = (student.id, shift["shift_date"], shift["start_time"], shift["end_time"])
                self.assertNotIn(key, seen)
                seen.add(key)
                for other in run["shifts"]:
                    if shift["id"] != other["id"] and shift["student_id"] == other["student_id"] and shift["shift_date"] == other["shift_date"]:
                        self.assertFalse(shift["start_time"] < other["end_time"] and other["start_time"] < shift["end_time"])
            for requirement in db.scalars(select(StaffingRequirement)):
                for minute in range(requirement.start_time.hour * 60, requirement.end_time.hour * 60, 30):
                    instant = f"{minute // 60:02d}:{minute % 60:02d}:00"
                    covered = sum(s["requirement_id"] == requirement.id and s["start_time"] <= instant < s["end_time"] for s in run["shifts"])
                    missing = sum(g["missing_count"] for g in run["unfilled"] if g["staffing_requirement_id"] == requirement.id and g["start_time"] <= instant < g["end_time"])
                    self.assertLessEqual(covered, requirement.required_count)
                    self.assertEqual(covered + missing, requirement.required_count)
        self.assertEqual(sum(totals.values()), run["summary"]["assigned_staff_minutes"])
        self.assertEqual(run["summary"]["required_staff_minutes"], run["summary"]["assigned_staff_minutes"] + run["summary"]["unfilled_staff_minutes"])
        self.assertNotIn(6, totals)
        self.assertNotIn(7, totals)

    def test_roles_department_run_isolation_and_saved_version_preservation(self):
        self.scenario()
        run = self.generate()
        second = self.generate()
        self.assertNotEqual(run["id"], second["id"])
        comparable = lambda shifts: [{key: value for key, value in shift.items() if key != "id"} for shift in shifts]
        self.assertEqual(comparable(run["shifts"]), comparable(second["shifts"]))
        self.assertEqual(len(self.request("GET", "/supervisor/schedules", user_id=4).json()), 2)
        self.assertEqual(self.request("GET", "/supervisor/schedules", user_id=5).json(), [])
        self.assertEqual(self.request("GET", f"/supervisor/schedules/{run['id']}", user_id=4).json(), run)
        for suffix in ["", "/coverage", "/employee-hours", "/unfilled"]:
            self.assertEqual(self.request("GET", f"/supervisor/schedules/{run['id']}" + suffix, user_id=5).status_code, 404)
            self.assertEqual(self.request("GET", f"/supervisor/schedules/{run['id']}" + suffix, user_id=4).status_code, 200)
        self.assertEqual(self.request("POST", "/supervisor/schedules", json={"week_start": "2026-10-19"}).status_code, 403)
        self.assertEqual(self.request("POST", "/supervisor/schedules", user_id=4, json={"week_start": "2026-10-20"}).status_code, 422)
        self.assertEqual(self.request("POST", "/supervisor/schedules", user_id=4, json={"week_start": "2026-10-19", "department_id": 2}).status_code, 422)
        for path in ["/supervisor/locations", "/supervisor/requirements", "/supervisor/schedules"]:
            self.assertEqual(self.request("GET", path).status_code, 403)
            self.assertEqual(self.client.get("/api" + path).status_code, 401)

    def test_student_preview_only_own_shifts_and_latest_version(self):
        self.scenario()
        self.assertIsNone(self.request("GET", "/students/me/schedule").json()["run_id"])
        first = self.generate()
        second = self.generate()
        preview = self.request("GET", "/students/me/schedule").json()
        self.assertEqual(preview["run_id"], second["id"])
        self.assertTrue(all(shift["student_id"] == 1 for shift in preview["shifts"]))
        self.assertNotIn("summary", preview)
        self.assertIsNone(self.request("GET", "/students/me/schedule", user_id=3).json()["run_id"])
        self.assertEqual(self.request("GET", "/students/me/schedule?week_start=2026-10-20").status_code, 422)
        self.assertEqual(self.request("PUT", f"/supervisor/schedules/{first['id']}", json={}).status_code, 405)

    def test_saved_drafts_keep_history_after_configuration_changes(self):
        self.scenario()
        run = self.generate()
        requirement_id = run["shifts"][0]["requirement_id"]
        self.assertEqual(self.request("DELETE", f"/supervisor/requirements/{requirement_id}", user_id=4).status_code, 409)
        location_id = run["shifts"][0]["location_id"]
        self.request("PUT", f"/supervisor/locations/{location_id}", user_id=4, json={"name": "Renamed inactive", "is_active": False})
        self.request("PATCH", "/supervisor/employees/1/scheduling", user_id=4, json={"is_active": False})
        updated = self.generate()
        self.assertTrue(all(shift["location_id"] != location_id and shift["student_id"] != 1 for shift in updated["shifts"]))
        self.assertEqual(self.request("GET", f"/supervisor/schedules/{run['id']}", user_id=4).json(), run)

    def test_failure_rolls_back_entire_draft(self):
        self.scenario()
        with patch("app.services.scheduling.AssignedShift", side_effect=RuntimeError("simulated persistence failure")):
            with self.assertRaises(RuntimeError):
                self.generate()
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ScheduleRun)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AssignedShift)), 0)

    def test_demo_seed_repeats_without_duplicate_data_and_generates(self):
        from app.seed_scheduling import seed_data, SUPERVISOR_EMAIL
        from app.services.scheduling import generate_run
        with self.app.state.session_factory() as db:
            seed_data(db, phase2.PASSWORD)
            first_counts = tuple(db.scalar(select(func.count()).select_from(model)) for model in
                                 (User, Availability, ClassSchedule, WorkLocation, StaffingRequirement, LocationEligibility))
            seed_data(db, phase2.PASSWORD)
            self.assertEqual(first_counts, tuple(db.scalar(select(func.count()).select_from(model)) for model in
                             (User, Availability, ClassSchedule, WorkLocation, StaffingRequirement, LocationEligibility)))
            supervisor = db.scalar(select(User).where(User.email == SUPERVISOR_EMAIL))
            run = generate_run(db, supervisor, date(2026, 10, 19))
            self.assertGreater(len(run.shifts), 0)
            self.assertGreater(len(run.unfilled), 0)
            self.assertEqual(run.summary["required_staff_minutes"], 44 * 60)


class UpgradePreservationTests(unittest.TestCase):
    def test_phase2_users_survive_additive_migration(self):
        with TemporaryDirectory(dir=BACKEND_DIR) as directory:
            url = "sqlite:///" + str(Path(directory) / "upgrade.db")
            with patch.dict(os.environ, {"DATABASE_URL": url}):
                config = Config(str(BACKEND_DIR / "alembic.ini"))
                command.upgrade(config, "0001")
                engine, _ = create_session_factory(url)
                with engine.begin() as conn:
                    conn.exec_driver_sql("INSERT INTO departments (id,name,description) VALUES (1,'Preserved','Existing data')")
                    conn.exec_driver_sql("INSERT INTO users (id,full_name,email,password_hash,role,department_id,max_weekly_hours,created_at) VALUES (1,'Original','original@example.com','hash','student',1,20,'2026-01-01')")
                engine.dispose()
                command.upgrade(config, "head")
                engine, factory = create_session_factory(url)
                with factory() as db:
                    self.assertEqual(db.get(User, 1).full_name, "Original")
                    self.assertTrue(db.get(User, 1).is_active)
                    self.assertEqual(db.get(Department, 1).timezone, "America/Chicago")
                engine.dispose()
                command.check(config)


if __name__ == "__main__":
    unittest.main()
