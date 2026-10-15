from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, student_only, supervisor_only
from app.models import User
from app.schemas import UserOut
from app.schemas.scheduling import (EmployeeSchedulingInput, GenerateInput, LocationInput,
    LocationOut, RequirementInput, RequirementOut, RunDetail, RunOut, StudentPreview, UnfilledOut)
from app.services import scheduling

router = APIRouter(prefix="/api")


@router.get("/supervisor/locations", response_model=list[LocationOut])
def locations(user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.locations(db, user.department_id)


@router.post("/supervisor/locations", response_model=LocationOut, status_code=201)
def add_location(data: LocationInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.save_location(db, user.department_id, data)


@router.get("/supervisor/locations/{location_id}", response_model=LocationOut)
def location(location_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.location_data(scheduling.location(db, user.department_id, location_id))


@router.put("/supervisor/locations/{location_id}", response_model=LocationOut)
def edit_location(location_id: int, data: LocationInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.save_location(db, user.department_id, data, location_id)


@router.get("/students/me/locations")
def student_locations(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return [{key: item[key] for key in ("id", "name", "description", "is_active")}
            for item in scheduling.locations(db, user.department_id)
            if item["is_active"] and user.id in item["eligible_student_ids"]]


@router.patch("/supervisor/employees/{student_id}/scheduling", response_model=UserOut)
def employee_status(student_id: int, data: EmployeeSchedulingInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.update_student_status(db, user, student_id, data.is_active)


@router.get("/supervisor/requirements", response_model=list[RequirementOut])
def requirements(user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.requirements(db, user.department_id)


@router.post("/supervisor/requirements", response_model=RequirementOut, status_code=201)
def add_requirement(data: RequirementInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.save_requirement(db, user.department_id, data)


@router.get("/supervisor/requirements/{requirement_id}", response_model=RequirementOut)
def requirement(requirement_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.owned_requirement(db, user.department_id, requirement_id)


@router.put("/supervisor/requirements/{requirement_id}", response_model=RequirementOut)
def edit_requirement(requirement_id: int, data: RequirementInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.save_requirement(db, user.department_id, data, requirement_id)


@router.delete("/supervisor/requirements/{requirement_id}", status_code=204)
def remove_requirement(requirement_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    scheduling.delete_requirement(db, user.department_id, requirement_id)
    return Response(status_code=204)


@router.post("/supervisor/schedules", response_model=RunDetail, status_code=201)
def generate(data: GenerateInput, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.run_detail(scheduling.generate_run(db, user, data.week_start))


@router.get("/supervisor/schedules", response_model=list[RunOut])
def schedules(user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.list_runs(db, user.department_id)


@router.get("/supervisor/schedules/{run_id}", response_model=RunDetail)
def schedule(run_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.run_detail(scheduling.owned_run(db, user.department_id, run_id))


@router.get("/supervisor/schedules/{run_id}/unfilled", response_model=list[UnfilledOut])
def unfilled(run_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return scheduling.owned_run(db, user.department_id, run_id).unfilled


@router.get("/supervisor/schedules/{run_id}/coverage")
def coverage(run_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    summary = scheduling.owned_run(db, user.department_id, run_id).summary
    return {key: summary[key] for key in ("required_staff_minutes", "assigned_staff_minutes", "unfilled_staff_minutes",
        "coverage_percent", "total_assigned_hours", "required_slot_positions", "unfilled_slot_positions", "slot_minutes")}


@router.get("/supervisor/schedules/{run_id}/employee-hours")
def hours(run_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    summary = scheduling.owned_run(db, user.department_id, run_id).summary
    return [{"student_id": int(key), "student_name": summary["employee_names"][key], "assigned_hours": value / 60}
            for key, value in summary["employee_minutes"].items()]


@router.get("/students/me/schedule", response_model=StudentPreview)
def preview(week_start: date | None = None, user: User = Depends(student_only), db: Session = Depends(get_db)):
    if week_start and week_start.weekday() != 0:
        raise HTTPException(422, "Week start must be Monday.")
    return scheduling.student_preview(db, user, week_start)
