"""Relational models; migrations own schema creation."""

from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, JSON, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    users: Mapped[list["User"]] = relationship(back_populates="department")
    timezone: Mapped[str] = mapped_column(String(80), default="America/Chicago", server_default="America/Chicago")
    locations: Mapped[list["WorkLocation"]] = relationship(back_populates="department")
    schedule_runs: Mapped[list["ScheduleRun"]] = relationship(back_populates="department")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'supervisor')", name="valid_role"),
        CheckConstraint("max_weekly_hours >= 0 AND max_weekly_hours <= 40", name="valid_hours"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    max_weekly_hours: Mapped[int] = mapped_column(default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    department: Mapped[Department] = relationship(back_populates="users")
    classes: Mapped[list["ClassSchedule"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    availability: Mapped[list["Availability"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class ClassSchedule(Base):
    __tablename__ = "class_schedules"
    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="class_valid_day"),
        CheckConstraint("start_time < end_time", name="class_valid_times"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_name: Mapped[str] = mapped_column(String(120))
    day_of_week: Mapped[int]
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    student: Mapped[User] = relationship(back_populates="classes")


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="availability_valid_day"),
        CheckConstraint("start_time < end_time", name="availability_valid_times"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[int]
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    student: Mapped[User] = relationship(back_populates="availability")


class WorkLocation(Base):
    __tablename__ = "work_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    department: Mapped[Department] = relationship(back_populates="locations")
    eligibility: Mapped[list["LocationEligibility"]] = relationship(cascade="all, delete-orphan")
    requirements: Mapped[list["StaffingRequirement"]] = relationship(back_populates="location")


class LocationEligibility(Base):
    __tablename__ = "location_eligibility"
    location_id: Mapped[int] = mapped_column(ForeignKey("work_locations.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)


class StaffingRequirement(Base):
    __tablename__ = "staffing_requirements"
    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="staffing_valid_day"),
        CheckConstraint("start_time < end_time", name="staffing_valid_times"),
        CheckConstraint("required_count >= 1 AND required_count <= 50", name="staffing_valid_count"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("work_locations.id"), index=True)
    day_of_week: Mapped[int]
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    required_count: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    location: Mapped[WorkLocation] = relationship(back_populates="requirements")


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (CheckConstraint("status = 'draft'", name="run_draft_only"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    algorithm_version: Mapped[str] = mapped_column(String(60))
    summary: Mapped[dict] = mapped_column(JSON)
    department: Mapped[Department] = relationship(back_populates="schedule_runs")
    shifts: Mapped[list["AssignedShift"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    unfilled: Mapped[list["UnfilledRequirement"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AssignedShift(Base):
    __tablename__ = "assigned_shifts"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="shift_valid_times"),
        CheckConstraint("duration_minutes > 0", name="shift_valid_duration"),
        CheckConstraint("status = 'draft'", name="shift_draft_only"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_run_id: Mapped[int] = mapped_column(ForeignKey("schedule_runs.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("work_locations.id"), index=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("staffing_requirements.id"), index=True)
    shift_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="draft")
    student_name: Mapped[str] = mapped_column(String(120))
    location_name: Mapped[str] = mapped_column(String(120))
    run: Mapped[ScheduleRun] = relationship(back_populates="shifts")


class UnfilledRequirement(Base):
    __tablename__ = "unfilled_requirements"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="unfilled_valid_times"),
        CheckConstraint("missing_count > 0", name="unfilled_positive_count"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_run_id: Mapped[int] = mapped_column(ForeignKey("schedule_runs.id", ondelete="CASCADE"), index=True)
    staffing_requirement_id: Mapped[int] = mapped_column(ForeignKey("staffing_requirements.id"), index=True)
    shift_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    missing_count: Mapped[int]
    reason: Mapped[str] = mapped_column(Text)
    location_id: Mapped[int] = mapped_column(ForeignKey("work_locations.id"))
    location_name: Mapped[str] = mapped_column(String(120))
    run: Mapped[ScheduleRun] = relationship(back_populates="unfilled")
