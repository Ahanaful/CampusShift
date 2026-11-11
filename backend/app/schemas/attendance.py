from datetime import datetime
from typing import Literal
from pydantic import Field
from app.schemas import Input

RecordStatus = Literal["missing", "active", "completed", "corrected"]
CorrectionStatus = Literal["pending", "approved", "rejected"]


class ClockInInput(Input):
    assigned_shift_id: int = Field(gt=0, strict=True)


class CorrectionInput(ClockInInput):
    proposed_clock_in: datetime
    proposed_clock_out: datetime
    reason: str = Field(min_length=1, max_length=1000)
    clock_in_fold: int = Field(default=0, ge=0, le=1, strict=True)
    clock_out_fold: int = Field(default=0, ge=0, le=1, strict=True)


class CorrectionDecision(Input):
    status: Literal["approved", "rejected"]
    reviewer_note: str = Field(default="", max_length=1000)
