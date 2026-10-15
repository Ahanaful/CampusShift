from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=1, max_length=120)]
Hours = Annotated[int, Field(ge=0, le=40, strict=True)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    # Password spaces are meaningful and must not be trimmed.
    model_config = ConfigDict(extra="forbid")


class Register(Login):
    full_name: Name
    department_id: int = Field(gt=0)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: Literal["student", "supervisor"]
    department_id: int
    max_weekly_hours: int
    is_active: bool
    created_at: datetime


class ProfileUpdate(Input):
    full_name: Name
    max_weekly_hours: Hours


class HoursUpdate(Input):
    max_weekly_hours: Hours


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    timezone: str


class WindowInput(Input):
    day_of_week: int = Field(ge=0, le=6, strict=True)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def valid_range(self):
        for value in (self.start_time, self.end_time):
            if value.tzinfo is not None or value.second or value.microsecond:
                raise ValueError("Use local campus times with minute precision")
        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time; split overnight windows by day")
        return self


class ClassInput(WindowInput):
    course_name: Name


class WindowOut(WindowInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int


class ClassOut(WindowOut):
    course_name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
