"""Configuration shared by API, migrations and explicit developer commands."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int
    cors_origins: tuple[str, ...]
    clock_in_early_minutes: int = 15
    clock_in_late_minutes: int = 30
    attendance_late_grace_minutes: int = 5

    @classmethod
    def from_env(cls):
        load_dotenv(BACKEND_DIR / ".env", override=False)
        database_url = os.getenv("DATABASE_URL", "sqlite:///./campusshift.db")
        if database_url.startswith("sqlite:///./"):
            database_url = "sqlite:///" + str(BACKEND_DIR / database_url.removeprefix("sqlite:///./"))
        minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
        if not 1 <= minutes <= 60:
            raise ValueError("JWT_EXPIRE_MINUTES must be between 1 and 60")
        attendance = {name: int(os.getenv(key, str(default))) for name, key, default in (
            ("clock_in_early_minutes", "CLOCK_IN_EARLY_MINUTES", 15),
            ("clock_in_late_minutes", "CLOCK_IN_LATE_MINUTES", 30),
            ("attendance_late_grace_minutes", "ATTENDANCE_LATE_GRACE_MINUTES", 5))}
        if any(not 0 <= value <= 240 for value in attendance.values()):
            raise ValueError("Attendance window/grace settings must be between 0 and 240 minutes")
        return cls(
            database_url=database_url,
            jwt_secret=os.getenv("JWT_SECRET", ""),
            jwt_expire_minutes=minutes,
            cors_origins=tuple(origin.strip() for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",") if origin.strip()),
            **attendance,
        )
