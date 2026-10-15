from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, student_only, supervisor_only
from app.core.security import issue_token, require_secret
from app.models import Availability, ClassSchedule, User
from app.schemas import (ClassInput, ClassOut, DepartmentOut, HoursUpdate, Login,
                         ProfileUpdate, Register, TokenOut, UserOut, WindowInput, WindowOut)
from app.services import accounts, windows

router = APIRouter(prefix="/api")


@router.get("/departments", response_model=list[DepartmentOut])
def departments(db: Session = Depends(get_db)):
    return accounts.list_departments(db)


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(data: Register, request: Request, db: Session = Depends(get_db)):
    require_secret(request.app.state.settings)
    return accounts.create_student(db, data)


@router.post("/auth/login", response_model=TokenOut)
def login(data: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    require_secret(request.app.state.settings)
    response.headers["Cache-Control"] = "no-store"
    return issue_token(accounts.authenticate(db, data.email, data.password).id, request.app.state.settings)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/students/me", response_model=UserOut)
def update_profile(data: ProfileUpdate, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return accounts.update_profile(db, user, data)


@router.get("/students/me/classes", response_model=list[ClassOut])
def classes(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.list_windows(db, ClassSchedule, user.id)


@router.post("/students/me/classes", response_model=ClassOut, status_code=201)
def add_class(data: ClassInput, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.save_window(db, ClassSchedule, user.id, data)


@router.put("/students/me/classes/{entry_id}", response_model=ClassOut)
def edit_class(entry_id: int, data: ClassInput, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.save_window(db, ClassSchedule, user.id, data, entry_id)


@router.delete("/students/me/classes/{entry_id}", status_code=204)
def remove_class(entry_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    windows.delete_window(db, ClassSchedule, user.id, entry_id)
    return Response(status_code=204)


@router.get("/students/me/availability", response_model=list[WindowOut])
def availability(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.list_windows(db, Availability, user.id)


@router.post("/students/me/availability", response_model=WindowOut, status_code=201)
def add_availability(data: WindowInput, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.save_window(db, Availability, user.id, data)


@router.put("/students/me/availability/{entry_id}", response_model=WindowOut)
def edit_availability(entry_id: int, data: WindowInput, user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.save_window(db, Availability, user.id, data, entry_id)


@router.delete("/students/me/availability/{entry_id}", status_code=204)
def remove_availability(entry_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    windows.delete_window(db, Availability, user.id, entry_id)
    return Response(status_code=204)


@router.get("/students/me/conflicts")
def conflicts(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return windows.conflicts(db, user.id)


@router.get("/supervisor/department", response_model=DepartmentOut)
def department(user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return accounts.get_department(db, user.department_id)


@router.get("/supervisor/employees", response_model=list[UserOut])
def employees(user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return accounts.list_employees(db, user)


@router.get("/supervisor/employees/{student_id}", response_model=UserOut)
def employee(student_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return accounts.department_student(db, user, student_id)


@router.patch("/supervisor/employees/{student_id}", response_model=UserOut)
def employee_hours(student_id: int, data: HoursUpdate, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    return accounts.update_employee_hours(db, user, student_id, data.max_weekly_hours)


@router.get("/supervisor/employees/{student_id}/classes", response_model=list[ClassOut])
def employee_classes(student_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    accounts.department_student(db, user, student_id)
    return windows.list_windows(db, ClassSchedule, student_id)


@router.get("/supervisor/employees/{student_id}/availability", response_model=list[WindowOut])
def employee_availability(student_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    accounts.department_student(db, user, student_id)
    return windows.list_windows(db, Availability, student_id)


@router.get("/supervisor/employees/{student_id}/conflicts")
def employee_conflicts(student_id: int, user: User = Depends(supervisor_only), db: Session = Depends(get_db)):
    accounts.department_student(db, user, student_id)
    return windows.conflicts(db, student_id)
