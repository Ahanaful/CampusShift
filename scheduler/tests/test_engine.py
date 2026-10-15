from dataclasses import replace
from datetime import date
import unittest

from scheduler.engine import Requirement, Student, Window, generate

MONDAY = date(2026, 10, 19)


class SchedulerTests(unittest.TestCase):
    def student(self, student_id=1, **changes):
        return replace(Student(student_id, 1, 1200, frozenset({1, 2}), (Window(0, 540, 1020),)), **changes)

    def demand(self, requirement_id=1, **changes):
        return replace(Requirement(requirement_id, 1, 1, 0, 540, 720, 1), **changes)

    def run_schedule(self, students=None, requirements=None):
        return generate(1, MONDAY, tuple(students if students is not None else [self.student()]),
                        tuple(requirements if requirements is not None else [self.demand()]))

    def test_available_eligible_and_merge_contiguous(self):
        result = self.run_schedule()
        self.assertEqual(len(result.assignments), 1)
        self.assertEqual((result.assignments[0].start, result.assignments[0].end), (540, 720))
        self.assertEqual(result.summary["coverage_percent"], 100)

    def test_missing_availability_and_inactive_and_ineligible_and_other_department(self):
        for changes in [{"availability": ()}, {"active": False}, {"eligible_locations": frozenset()}, {"department_id": 2}]:
            with self.subTest(changes=changes):
                result = self.run_schedule([self.student(**changes)])
                self.assertEqual(result.assignments, ())
                self.assertTrue(result.unfilled)

    def test_class_overlap_and_half_open_boundary(self):
        result = self.run_schedule([self.student(classes=(Window(0, 540, 600),))])
        self.assertEqual(result.assignments[0].start, 600)
        self.assertEqual(result.summary["assigned_staff_minutes"], 120)
        self.assertEqual(self.run_schedule([self.student(classes=(Window(0, 480, 540),))]).summary["coverage_percent"], 100)

    def test_partial_slot_availability_does_not_leak(self):
        result = self.run_schedule([self.student(availability=(Window(0, 555, 645),))])
        self.assertEqual([(a.start, a.end) for a in result.assignments], [(570, 630)])

    def test_multiple_locations_never_double_book(self):
        result = self.run_schedule(requirements=[self.demand(), self.demand(2, location_id=2)])
        self.assertEqual(result.summary["assigned_staff_minutes"], 180)
        self.assertEqual(result.summary["unfilled_staff_minutes"], 180)
        for a in result.assignments:
            for b in result.assignments:
                if a is not b:
                    self.assertFalse(a.student_id == b.student_id and a.start < b.end and b.start < a.end)

    def test_weekly_cap_and_zero_cap(self):
        self.assertEqual(self.run_schedule([self.student(max_minutes=60)]).summary["assigned_staff_minutes"], 60)
        self.assertEqual(self.run_schedule([self.student(max_minutes=0)]).assignments, ())

    def test_no_students_and_no_demand(self):
        result = self.run_schedule([])
        self.assertEqual(result.summary["coverage_percent"], 0)
        self.assertIn("No active", result.unfilled[0].reason)
        self.assertEqual(self.run_schedule(requirements=[]).summary["coverage_percent"], 100)

    def test_fair_deterministic_and_input_order_independent(self):
        students = [self.student(1), self.student(2), self.student(3)]
        result = self.run_schedule(students)
        self.assertEqual(result, self.run_schedule(list(reversed(students))))
        self.assertEqual(result, self.run_schedule(students))
        self.assertEqual(set(result.summary["employee_minutes"].values()), {60})

    def test_historical_hours_and_week_rotation_break_ties(self):
        demand = [self.demand(end=570)]
        result = self.run_schedule([self.student(1, prior_minutes=100), self.student(2, prior_minutes=0)], demand)
        self.assertEqual(result.assignments[0].student_id, 2)
        students = (self.student(1), self.student(2))
        first = generate(1, MONDAY, students, tuple(demand)).assignments[0].student_id
        next_week = generate(1, date(2026, 10, 26), students, tuple(demand)).assignments[0].student_id
        self.assertNotEqual(first, next_week)

    def test_fairness_bands_reduce_fragmentation(self):
        result = self.run_schedule([self.student(1), self.student(2)], [self.demand(end=660)])
        self.assertEqual(sorted(a.end - a.start for a in result.assignments), [60, 60])

    def test_scarce_location_gets_specialist(self):
        result = self.run_schedule([self.student(1), self.student(2, eligible_locations=frozenset({1}))],
                                   [self.demand(end=570), self.demand(2, location_id=2, end=570)])
        self.assertEqual(result.summary["coverage_percent"], 100)

    def test_invalid_inputs_and_overlapping_demand(self):
        for changes in [{"start": 720, "end": 540}, {"start": 541}, {"count": 0}, {"day": 7}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_schedule(requirements=[self.demand(**changes)])
        with self.assertRaises(ValueError):
            generate(1, date(2026, 10, 20), (), ())
        with self.assertRaises(ValueError):
            self.run_schedule(requirements=[self.demand(), self.demand(2)])

    def test_inactive_and_other_department_requirements_ignored(self):
        self.assertEqual(self.run_schedule(requirements=[self.demand(active=False), self.demand(2, department_id=2)]).assignments, ())


if __name__ == "__main__":
    unittest.main()
