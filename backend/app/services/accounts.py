from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import DUMMY_HASH, hasher, verify_password
from app.models import Department, User


def list_departments(db):
    return list(db.scalars(select(Department).order_by(Department.name)))


def get_department(db, department_id):
    return db.get(Department, department_id)


def update_profile(db, user, data):
    user.full_name = data.full_name
    user.max_weekly_hours = data.max_weekly_hours
    db.commit()
    return user


def list_employees(db, supervisor):
    return list(db.scalars(select(User).where(User.role == "student", User.department_id == supervisor.department_id)
                           .order_by(User.full_name, User.id)))


def update_employee_hours(db, supervisor, student_id, hours):
    employee = department_student(db, supervisor, student_id)
    employee.max_weekly_hours = hours
    db.commit()
    return employee


def create_student(db, data):
    if not db.get(Department, data.department_id):
        raise HTTPException(422, "Choose an existing department.")
    user = User(full_name=data.full_name, email=str(data.email).lower(),
                password_hash=hasher.hash(data.password), role="student",
                department_id=data.department_id, max_weekly_hours=20)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None
    return user


def authenticate(db, email, password):
    user = db.scalar(select(User).where(User.email == str(email).lower()))
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.", headers={"WWW-Authenticate": "Bearer"})
    return user


def department_student(db, supervisor, student_id):
    user = db.scalar(select(User).where(User.id == student_id, User.role == "student",
                                       User.department_id == supervisor.department_id))
    if not user:
        raise HTTPException(404, "Employee not found.")
    return user
