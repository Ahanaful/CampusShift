"""Relational models; migrations own schema creation."""

from datetime import datetime, time, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    users: Mapped[list["User"]] = relationship(back_populates="department")


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
