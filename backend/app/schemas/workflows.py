from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas import Input

LeaveStatus = Literal["pending", "approved", "rejected", "cancelled"]


class TimeOffInput(Input):
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date")
        return self


class DecisionInput(Input):
    status: Literal["approved", "rejected"]
    decision_note: str = Field(default="", max_length=1000)


class TimeOffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    department_id: int
    start_date: date
    end_date: date
    reason: str
    status: LeaveStatus
    reviewer_id: int | None
    decision_note: str
    reviewed_at: datetime | None
    created_at: datetime
    cancelled_at: datetime | None

    @field_validator("created_at", "reviewed_at", "cancelled_at")
    @classmethod
    def utc_audit(cls, value):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class VersionInput(Input):
    expected_version: int = Field(ge=1, strict=True)


class ReassignInput(VersionInput):
    student_id: int = Field(gt=0, strict=True)


class AddShiftInput(VersionInput):
    student_id: int = Field(gt=0, strict=True)
    requirement_id: int = Field(gt=0, strict=True)
    shift_date: date
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):(?:00|30)(?::00)?$")
    end_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):(?:00|30)(?::00)?$")


class PublishInput(VersionInput):
    acknowledge_uncovered: bool = Field(default=False, strict=True)
    expected_current_published_id: int | None = Field(default=None, gt=0, strict=True)
