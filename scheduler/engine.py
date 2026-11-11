"""Deterministic greedy scheduling using integer minutes and half-open slots."""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

ALGORITHM_VERSION = "greedy-30m-v2-leave"
SLOT_MINUTES = 30


@dataclass(frozen=True)
class Window:
    day: int
    start: int
    end: int


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


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
    approved_time_off: tuple[DateRange, ...] = ()


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


def assignment_error(student, requirement, shift_date, start, end, assignments, assigned_minutes):
    """Shared hard constraints for generation, manual editing and publication."""
    if student.department_id != requirement.department_id or not student.active:
        return "Student must be active and belong to this department"
    if requirement.location_id not in student.eligible_locations:
        return "Student is not eligible for this active work location"
    if shift_date.weekday() != requirement.day or not requirement.start <= start < end <= requirement.end:
        return "Shift must fit the staffing requirement on the correct day"
    if start % SLOT_MINUTES or end % SLOT_MINUTES:
        return "Shift must use 30-minute boundaries"
    if any(leave.start <= shift_date <= leave.end for leave in student.approved_time_off):
        return "Approved time off covers this date"
    if not any(w.day == requirement.day and w.start <= start and end <= w.end for w in student.availability):
        # Adjacent submitted windows form one continuous available interval.
        windows = sorted((w for w in student.availability if w.day == requirement.day), key=lambda w: w.start)
        cursor = start
        for window in windows:
            if window.start <= cursor < window.end:
                cursor = window.end
        if cursor < end:
            return "Submitted availability does not cover this shift"
    if any(w.day == requirement.day and w.start < end and start < w.end for w in student.classes):
        return "Shift conflicts with a class"
    if any(a.student_id == student.id and a.shift_date == shift_date and a.start < end and start < a.end for a in assignments):
        return "Student already has an overlapping shift"
    if assigned_minutes + end - start > student.max_minutes:
        return "Shift would exceed the student's maximum weekly hours"
    return None


def summarize(week_start, students, requirements, assignments, reasons=None):
    """Measure fixed assignments against saved demand; never allocate employees."""
    reasons = reasons or {}
    gaps = []
    required_minutes = 0
    for requirement in sorted(requirements, key=lambda r: r.id):
        shift_date = week_start + timedelta(days=requirement.day)
        for start in range(requirement.start, requirement.end, SLOT_MINUTES):
            count = sum(a.requirement_id == requirement.id and a.shift_date == shift_date
                        and a.start <= start < a.end for a in assignments)
            if count > requirement.count:
                raise ValueError("Staffing capacity exceeded for this position")
            required_minutes += SLOT_MINUTES * requirement.count
            if count < requirement.count:
                gaps.append(Unfilled(requirement.id, requirement.location_id, shift_date, start,
                    start + SLOT_MINUTES, requirement.count - count,
                    reasons.get((requirement.id, shift_date, start), "Unfilled staffing position; assign an eligible employee or acknowledge it at publication")))
    totals = {s.id: 0 for s in students}
    for assignment in assignments:
        totals[assignment.student_id] = totals.get(assignment.student_id, 0) + assignment.end - assignment.start
    filled = sum(totals.values())
    return Result(tuple(assignments), _merge(gaps, lambda u: (u.shift_date, u.location_id, u.requirement_id, u.missing_count, u.reason)), {
        "required_staff_minutes": required_minutes, "assigned_staff_minutes": filled,
        "unfilled_staff_minutes": required_minutes - filled,
        "coverage_percent": round(100 * filled / required_minutes, 2) if required_minutes else 100.0,
        "total_assigned_hours": filled / 60, "required_slot_positions": required_minutes // SLOT_MINUTES,
        "unfilled_slot_positions": (required_minutes - filled) // SLOT_MINUTES,
        "employee_minutes": {str(key): value for key, value in sorted(totals.items())}, "slot_minutes": SLOT_MINUTES,
    })


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
        for leave in student.approved_time_off:
            if type(leave.start) is not date or type(leave.end) is not date or leave.start > leave.end:
                raise ValueError("Invalid approved time-off date range")
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
        shift_date = week_start + timedelta(days=requirement.day)
        return assignment_error(student, requirement, shift_date, start, end, assigned, totals[student.id])

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
    reasons = {(gap.requirement_id, gap.shift_date, minute): gap.reason for gap in gaps for minute in range(gap.start, gap.end, SLOT_MINUTES)}
    return summarize(week_start, candidates, relevant, assignments, reasons)
