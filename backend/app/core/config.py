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
    environment: str = "development"
    db_pooling: str = "queue"
    db_connect_timeout: int = 5
    db_connect_attempts: int = 1
    db_connect_backoff_seconds: float = 1
    db_statement_timeout_ms: int = 0
    db_lock_timeout_ms: int = 0

    @property
    def database_options(self):
        return {"pooling": self.db_pooling, "connect_timeout": self.db_connect_timeout,
                "connect_attempts": self.db_connect_attempts,
                "connect_backoff": self.db_connect_backoff_seconds,
                "statement_timeout_ms": self.db_statement_timeout_ms,
                "lock_timeout_ms": self.db_lock_timeout_ms}

    @classmethod
    def from_env(cls):
        load_dotenv(BACKEND_DIR / ".env", override=False)
        database_url = os.getenv("DATABASE_URL", "sqlite:///./campusshift.db")
        # libpq reads the password from a protected passfile in deployment.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        environment = os.getenv("APP_ENV", "development")
        if environment not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        pooling = os.getenv("DB_POOLING", "queue")
        timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
        attempts = int(os.getenv("DB_CONNECT_ATTEMPTS", "1"))
        backoff = float(os.getenv("DB_CONNECT_BACKOFF_SECONDS", "1"))
        statement_timeout = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "0"))
        lock_timeout = int(os.getenv("DB_LOCK_TIMEOUT_MS", "0"))
        if not 0 <= statement_timeout <= 120000 or not 0 <= lock_timeout <= 120000:
            raise ValueError("Invalid database statement/lock timeout")
        if pooling not in {"queue", "null"} or not 1 <= timeout <= 30 or not 1 <= attempts <= 3 or not 0 <= backoff <= 2:
            raise ValueError("Invalid database pooling/connection retry configuration")
        if environment == "production":
            if not database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL with the psycopg driver")
            if len(os.getenv("JWT_SECRET", "").encode()) < 32:
                raise ValueError("Production requires a JWT_SECRET of at least 32 bytes")
            origins = os.getenv("CORS_ORIGINS", "")
            if any(not origin.strip().startswith("https://") for origin in origins.split(",") if origin.strip()):
                raise ValueError("Production CORS origins must use HTTPS")
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
            environment=environment,
            db_pooling=pooling, db_connect_timeout=timeout,
            db_connect_attempts=attempts, db_connect_backoff_seconds=backoff,
            db_statement_timeout_ms=statement_timeout, db_lock_timeout_ms=lock_timeout,
            **attendance,
        )
