"""Atomic draft edits and publication, reusing scheduler hard constraints."""
from datetime import datetime, time, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import AssignedShift, ScheduleEvent, ScheduleRun, UnfilledRequirement, WorkLocation
from app.services import scheduling
from scheduler.engine import Assignment, Requirement, assignment_error, summarize


def locked_draft(db, supervisor, run_id, expected_version):
    scheduling.reserve_write(db)
    run = scheduling.owned_run(db, supervisor.department_id, run_id)
    db.refresh(run)
    if run.status != "draft":
        raise HTTPException(409, "Only drafts can be edited or published. Generate a new draft to replace a published schedule.")
    if run.version != expected_version:
        raise HTTPException(409, "This schedule changed in another session. Refresh before trying again.")
    return run


def demand_for(run):
    return tuple(Requirement(r["id"], run.department_id, r["location_id"], r["day"], r["start"], r["end"], r["count"])
                 for r in run.summary["input_snapshot"]["requirements"])


def assignment_for(shift):
    return Assignment(shift.student_id, shift.requirement_id, shift.location_id, shift.shift_date,
                      scheduling.minutes(shift.start_time), scheduling.minutes(shift.end_time))


def validate_assignment(run, assignment, students, demand, other):
    student = next((s for s in students if s.id == assignment.student_id), None)
    requirement = next((r for r in demand if r.id == assignment.requirement_id), None)
    if not student:
        return "Student must belong to your department"
    if not requirement or assignment.location_id != requirement.location_id:
        return "Select a staffing position from this schedule's saved requirements"
    if assignment.shift_date != run.week_start + timedelta(days=requirement.day):
        return "Shift date must match this draft week and requirement"
    assigned = sum(a.end - a.start for a in other if a.student_id == student.id)
    return assignment_error(student, requirement, assignment.shift_date, assignment.start, assignment.end, other, assigned)


def validation_issues(db, run):
    _, _, inputs = scheduling.student_inputs(db, run.department_id)
    demand = demand_for(run)
    assignments = [assignment_for(shift) for shift in run.shifts]
    issues = []
    active_locations = {item.id for item in db.scalars(select(WorkLocation).where(
        WorkLocation.department_id == run.department_id, WorkLocation.is_active.is_(True)))}
    current_demand = {(r.id, r.location_id, r.day_of_week, scheduling.minutes(r.start_time), scheduling.minutes(r.end_time), r.required_count)
                      for r in scheduling.requirements(db, run.department_id) if r.is_active and r.location_id in active_locations}
    saved_demand = {(r.id, r.location_id, r.day, r.start, r.end, r.count) for r in demand}
    if current_demand != saved_demand:
        issues.append({"shift_id": None, "message": "Staffing demand changed since generation. Generate a new draft before publishing."})
    for index, assignment in enumerate(assignments):
        error = validate_assignment(run, assignment, inputs, demand, assignments[:index] + assignments[index + 1:])
        if error:
            issues.append({"shift_id": run.shifts[index].id, "student_name": run.shifts[index].student_name, "message": error})
    try:
        summarize(run.week_start, inputs, demand, assignments)
    except ValueError as error:
        issues.append({"shift_id": None, "message": str(error)})
    return issues


def recompute(db, run):
    people, locations, inputs = scheduling.student_inputs(db, run.department_id)
    result = summarize(run.week_start, inputs, demand_for(run), [assignment_for(s) for s in run.shifts])
    names = {**run.summary["employee_names"], **{str(p.id): p.full_name for p in people}}
    run.summary = {**run.summary, **result.summary, "employee_names": names, "manually_edited": True}
    location_names = {item.id: item.name for item in locations}
    old_names = {gap.location_id: gap.location_name for gap in run.unfilled}
    old_names.update({shift.location_id: shift.location_name for shift in run.shifts})
    run.unfilled.clear()
    db.flush()
    for gap in result.unfilled:
        run.unfilled.append(UnfilledRequirement(staffing_requirement_id=gap.requirement_id, location_id=gap.location_id,
            location_name=location_names.get(gap.location_id, old_names.get(gap.location_id, "Location")),
            shift_date=gap.shift_date, start_time=scheduling.clock(gap.start), end_time=scheduling.clock(gap.end),
            missing_count=gap.missing_count, reason=gap.reason))


def event(db, run, actor, action, details):
    db.add(ScheduleEvent(schedule_run_id=run.id, actor_id=actor.id, action=action, details=details))


def shift_snapshot(shift):
    return {"shift_id": shift.id, "student_id": shift.student_id, "location_id": shift.location_id,
            "requirement_id": shift.requirement_id, "shift_date": shift.shift_date.isoformat(),
            "start_time": shift.start_time.isoformat(), "end_time": shift.end_time.isoformat()}


def edit(db, supervisor, run_id, data, operation, shift_id=None):
    run = locked_draft(db, supervisor, run_id, data.expected_version)
    shift = next((s for s in run.shifts if s.id == shift_id), None) if shift_id else None
    if operation != "add" and shift is None:
        raise HTTPException(404, "Assigned shift not found in this draft")
    before = shift_snapshot(shift) if shift else None
    people, locations, inputs = scheduling.student_inputs(db, run.department_id)
    assignments = [assignment_for(s) for s in run.shifts if s is not shift]
    if operation != "remove":
        assignment = Assignment(data.student_id, data.requirement_id, 0, data.shift_date,
            scheduling.minutes(time.fromisoformat(data.start_time)), scheduling.minutes(time.fromisoformat(data.end_time))) if operation == "add" else Assignment(
            data.student_id, shift.requirement_id, shift.location_id, shift.shift_date,
            scheduling.minutes(shift.start_time), scheduling.minutes(shift.end_time))
        demand = demand_for(run)
        requirement = next((r for r in demand if r.id == assignment.requirement_id), None)
        if operation == "add" and requirement:
            from dataclasses import replace
            assignment = replace(assignment, location_id=requirement.location_id)
        if requirement:
            current = scheduling.owned_requirement(db, run.department_id, requirement.id)
            if not current.is_active or (current.location_id, current.day_of_week, scheduling.minutes(current.start_time),
                    scheduling.minutes(current.end_time), current.required_count) != (
                    requirement.location_id, requirement.day, requirement.start, requirement.end, requirement.count):
                raise HTTPException(409, "This staffing requirement changed. Generate a new draft before adding or reassigning employees.")
        error = validate_assignment(run, assignment, inputs, demand, assignments)
        if error:
            raise HTTPException(422, error)
        try:
            summarize(run.week_start, inputs, demand, assignments + [assignment])
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        person = next(p for p in people if p.id == data.student_id)
        if operation == "add":
            shift = AssignedShift(student_id=person.id, student_name=person.full_name, requirement_id=assignment.requirement_id,
                location_id=assignment.location_id, location_name=next(l.name for l in locations if l.id == assignment.location_id),
                shift_date=assignment.shift_date, start_time=scheduling.clock(assignment.start), end_time=scheduling.clock(assignment.end),
                duration_minutes=assignment.end - assignment.start, status="draft")
            run.shifts.append(shift)
        else:
            shift.student_id = person.id
            shift.student_name = person.full_name
    else:
        run.shifts.remove(shift)
    try:
        recompute(db, run)
        run.version += 1
        event(db, run, supervisor, operation, {"before": before,
              "after": shift_snapshot(shift) if operation != "remove" else None, "version": run.version})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return run


def publish(db, supervisor, run_id, data):
    run = locked_draft(db, supervisor, run_id, data.expected_version)
    issues = validation_issues(db, run)
    if issues:
        raise HTTPException(422, "Resolve schedule conflicts before publishing: " + "; ".join(issue["message"] for issue in issues))
    if run.summary["unfilled_staff_minutes"] and not data.acknowledge_uncovered:
        raise HTTPException(409, "Explicitly acknowledge uncovered staffing positions before publishing")
    previous = db.scalar(select(ScheduleRun).where(ScheduleRun.department_id == run.department_id,
                          ScheduleRun.week_start == run.week_start, ScheduleRun.status == "published"))
    if (previous.id if previous else None) != data.expected_current_published_id:
        raise HTTPException(409, "The current published version changed. Refresh and review before replacing it.")
    try:
        if previous:
            previous.status = "archived"
            previous.version += 1
            for shift in previous.shifts:
                shift.status = "archived"
            event(db, previous, supervisor, "archived", {"replaced_by": run.id})
            db.flush()
        run.status = "published"
        run.published_by = supervisor.id
        run.published_at = datetime.now(timezone.utc)
        run.uncovered_acknowledged = data.acknowledge_uncovered
        run.version += 1
        for shift in run.shifts:
            shift.status = "published"
        event(db, run, supervisor, "published", {"replaces": previous.id if previous else None,
              "acknowledge_uncovered": data.acknowledge_uncovered, "unfilled_staff_minutes": run.summary["unfilled_staff_minutes"]})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return run
