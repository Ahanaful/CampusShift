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

    @classmethod
    def from_env(cls):
        load_dotenv(BACKEND_DIR / ".env", override=False)
        database_url = os.getenv("DATABASE_URL", "sqlite:///./campusshift.db")
        if database_url.startswith("sqlite:///./"):
            database_url = "sqlite:///" + str(BACKEND_DIR / database_url.removeprefix("sqlite:///./"))
        minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
        if not 1 <= minutes <= 60:
            raise ValueError("JWT_EXPIRE_MINUTES must be between 1 and 60")
        return cls(
            database_url=database_url,
            jwt_secret=os.getenv("JWT_SECRET", ""),
            jwt_expire_minutes=minutes,
            cors_origins=tuple(origin.strip() for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",") if origin.strip()),
        )
