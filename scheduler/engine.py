"""Deterministic greedy scheduling using integer minutes and half-open slots."""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

ALGORITHM_VERSION = "greedy-30m-v1"
SLOT_MINUTES = 30


@dataclass(frozen=True)
class Window:
    day: int
    start: int
    end: int


@dataclass(frozen=True)
class Student:
    id: int
    department_id: int
    max_minutes: int
    eligible_locations: frozenset[int] = frozenset()
    availability: tuple[Window, ...] = ()
    classes: tuple[Window, ...] = ()
    active: bool = True
    prior_minutes: int = 0


@dataclass(frozen=True)
class Requirement:
    id: int
    department_id: int
    location_id: int
    day: int
    start: int
    end: int
    count: int
    active: bool = True


@dataclass(frozen=True)
class Assignment:
    student_id: int
    requirement_id: int
    location_id: int
    shift_date: date
    start: int
    end: int


@dataclass(frozen=True)
class Unfilled:
    requirement_id: int
    location_id: int
    shift_date: date
    start: int
    end: int
    missing_count: int
    reason: str


@dataclass(frozen=True)
class Result:
    assignments: tuple[Assignment, ...]
    unfilled: tuple[Unfilled, ...]
    summary: dict = field(default_factory=dict)


def _valid_window(day, start, end):
    if any(type(value) is not int for value in (day, start, end)):
        raise ValueError("Window values must be integer minutes and weekdays")
    if not 0 <= day <= 6 or not 0 <= start < end < 1440:
        raise ValueError("Windows must start and end on the same local calendar day")


def _merge(rows, key):
    merged = []
    for row in sorted(rows, key=lambda row: (*key(row), row.start)):
        if merged and key(merged[-1]) == key(row) and merged[-1].end == row.start:
            merged[-1] = replace(merged[-1], end=row.end)
        else:
            merged.append(row)
    return tuple(merged)


def generate(department_id: int, week_start: date, students: tuple[Student, ...],
             requirements: tuple[Requirement, ...]) -> Result:
    """Create a new independent weekly draft; never mutate the supplied inputs.

    Requirements must use :00/:30 boundaries. Availability/classes retain minute
    precision; a full 30-minute staffing slot must be valid for assignment.
    """
    if type(week_start) is not date or week_start.weekday() != 0:
        raise ValueError("Week start must be a Monday date")
    if len({s.id for s in students}) != len(students) or len({r.id for r in requirements}) != len(requirements):
        raise ValueError("Duplicate student or requirement IDs")
    for student in students:
        if type(student.max_minutes) is not int or student.max_minutes < 0 or type(student.prior_minutes) is not int or student.prior_minutes < 0:
            raise ValueError("Weekly and prior minutes must be nonnegative integers")
        for window in (*student.classes, *student.availability):
            _valid_window(window.day, window.start, window.end)
    for requirement in requirements:
        _valid_window(requirement.day, requirement.start, requirement.end)
        if requirement.start % SLOT_MINUTES or requirement.end % SLOT_MINUTES:
            raise ValueError("Staffing requirements must use 30-minute boundaries")
        if type(requirement.count) is not int or not 1 <= requirement.count <= 50:
            raise ValueError("Headcount must be between 1 and 50")
    relevant = sorted((r for r in requirements if r.active and r.department_id == department_id), key=lambda r: r.id)
    for index, requirement in enumerate(relevant):
        if any(other.location_id == requirement.location_id and other.day == requirement.day
               and other.start < requirement.end and requirement.start < other.end
               for other in relevant[:index]):
            raise ValueError("Active staffing requirements overlap at the same location")
    candidates = sorted((s for s in students if s.department_id == department_id and s.active), key=lambda s: s.id)
    totals = {s.id: 0 for s in candidates}
    rotation = week_start.toordinal() // 7
    rotated = candidates[rotation % len(candidates):] + candidates[:rotation % len(candidates)] if candidates else []
    tie_rank = {s.id: index for index, s in enumerate(rotated)}
    assigned = []
    unfilled = []
    required_minutes = 0

    def exclusion(student, requirement, start, end):
        if requirement.location_id not in student.eligible_locations:
            return "No location-eligible employees"
        if not any(w.day == requirement.day and w.start <= start and end <= w.end for w in student.availability):
            return "Submitted availability does not cover this slot"
        if any(w.day == requirement.day and w.start < end and start < w.end for w in student.classes):
            return "Class conflicts"
        shift_date = week_start + timedelta(days=requirement.day)
        if any(a.student_id == student.id and a.shift_date == shift_date and a.start < end and start < a.end for a in assigned):
            return "Employees assigned at another location"
        if totals[student.id] + end - start > student.max_minutes:
            return "Weekly hour limits reached"
        return None

    for day in range(7):
        day_requirements = [r for r in relevant if r.day == day]
        for start in sorted({minute for r in day_requirements for minute in range(r.start, r.end, SLOT_MINUTES)}):
            end = start + SLOT_MINUTES
            pending = [r for r in day_requirements if r.start <= start and end <= r.end]
            # Recompute scarcity after each location, since allocations consume people.
            while pending:
                requirement = min(pending, key=lambda r: (sum(exclusion(s, r, start, end) is None for s in candidates) - r.count, r.id))
                pending.remove(requirement)
                required_minutes += (end - start) * requirement.count
                valid = [s for s in candidates if exclusion(s, requirement, start, end) is None]

                def ranking(student):
                    contiguous = any(a.student_id == student.id and a.requirement_id == requirement.id
                                     and a.shift_date == week_start + timedelta(days=day) and a.end == start for a in assigned)
                    # One-hour fairness bands allow short contiguous blocks
                    # instead of alternating every half hour solely on ties.
                    return (totals[student.id] // 60, student.prior_minutes, not contiguous,
                            totals[student.id], tie_rank[student.id], student.id)

                chosen = sorted(valid, key=ranking)[:requirement.count]
                exclusions = sorted({reason for s in candidates if (reason := exclusion(s, requirement, start, end))})
                for student in chosen:
                    assigned.append(Assignment(student.id, requirement.id, requirement.location_id,
                                               week_start + timedelta(days=day), start, end))
                    totals[student.id] += end - start
                missing = requirement.count - len(chosen)
                if missing:
                    reason = f"Only {len(chosen)} eligible employees for {requirement.count} required"
                    if exclusions:
                        reason += ": " + "; ".join(exclusions)
                    if not candidates:
                        reason = "No active department students"
                    unfilled.append(Unfilled(requirement.id, requirement.location_id, week_start + timedelta(days=day),
                                             start, end, missing, reason))
    assignments = _merge(assigned, lambda a: (a.shift_date, a.location_id, a.requirement_id, a.student_id))
    gaps = _merge(unfilled, lambda u: (u.shift_date, u.location_id, u.requirement_id, u.missing_count, u.reason))
    filled_minutes = sum(totals.values())
    return Result(assignments, gaps, {
        "required_staff_minutes": required_minutes, "assigned_staff_minutes": filled_minutes,
        "unfilled_staff_minutes": required_minutes - filled_minutes,
        "coverage_percent": round(100 * filled_minutes / required_minutes, 2) if required_minutes else 100.0,
        "total_assigned_hours": filled_minutes / 60,
        "required_slot_positions": required_minutes // SLOT_MINUTES,
        "unfilled_slot_positions": (required_minutes - filled_minutes) // SLOT_MINUTES,
        "employee_minutes": {str(student_id): minutes for student_id, minutes in sorted(totals.items())},
        "slot_minutes": SLOT_MINUTES,
    })
