from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas import Input, Name, WindowInput


class LocationInput(Input):
    name: Name
    description: str = Field(default="", max_length=1000)
    is_active: bool = Field(default=True, strict=True)
    eligible_student_ids: list[int] = Field(default_factory=list, max_length=1000)


class LocationOut(BaseModel):
    id: int
    department_id: int
    name: str
    description: str
    is_active: bool
    eligible_student_ids: list[int]


class RequirementInput(WindowInput):
    location_id: int = Field(gt=0, strict=True)
    required_count: int = Field(ge=1, le=50, strict=True)
    is_active: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def half_hour_boundaries(self):
        if self.start_time.minute % 30 or self.end_time.minute % 30:
            raise ValueError("Staffing times must use :00 or :30 boundaries")
        return self


class RequirementOut(RequirementInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int


class GenerateInput(Input):
    week_start: date

    @model_validator(mode="after")
    def monday(self):
        if self.week_start.weekday() != 0:
            raise ValueError("Select the Monday of the schedule week")
        # Leave space for converting all seven days without date overflow.
        if self.week_start.year > 9998:
            raise ValueError("Week is outside the supported date range")
        return self


class EmployeeSchedulingInput(Input):
    is_active: bool = Field(strict=True)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int
    week_start: date
    status: Literal["draft"]
    created_by: int
    created_at: datetime
    algorithm_version: str
    summary: dict

    @field_validator("created_at")
    @classmethod
    def utc_creation_time(cls, value):
        # SQLite drops tzinfo on round-trip. Creation instants are always UTC;
        # staffing dates/times remain department-local and are never converted.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    student_name: str
    location_id: int
    location_name: str
    requirement_id: int
    shift_date: date
    start_time: time
    end_time: time
    duration_minutes: int
    status: Literal["draft"]


class UnfilledOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    staffing_requirement_id: int
    location_id: int
    location_name: str
    shift_date: date
    start_time: time
    end_time: time
    missing_count: int
    reason: str


class RunDetail(RunOut):
    shifts: list[ShiftOut]
    unfilled: list[UnfilledOut]


class StudentPreview(BaseModel):
    run_id: int | None
    week_start: date | None
    status: Literal["draft"]
    timezone: str
    assigned_hours: float
    shifts: list[ShiftOut]
