"""FastAPI entry point. Migrations and seeding are explicit commands."""

from contextlib import asynccontextmanager
import logging
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.api.routes import router
from app.api.scheduling import router as scheduling_router
from app.api.workflows import router as workflows_router
from app.api.attendance import router as attendance_router
from app.core.config import Settings
from app.db.session import create_session_factory

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine, factory = create_session_factory(settings.database_url, **settings.database_options)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="CampusShift API", version="0.6.0", lifespan=lifespan,
                  docs_url=None if settings.environment == "production" else "/docs",
                  redoc_url=None if settings.environment == "production" else "/redoc",
                  openapi_url=None if settings.environment == "production" else "/openapi.json")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory

    @app.middleware("http")
    async def request_log(request, call_next):
        started = monotonic()
        response = await call_next(request)
        route = request.scope.get("route")
        # Log the route template, never raw paths, query strings, emails or tokens.
        logger.info("request method=%s route=%s status=%s duration_ms=%d",
                    request.method, getattr(route, "path", "unmatched"),
                    response.status_code, int((monotonic() - started) * 1000))
        return response
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Database unavailable. Check configuration and run database migrations."})

    @app.get("/")
    def welcome() -> dict[str, str]:
        return {"message": "Welcome to CampusShift!"}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "application": "CampusShift"}

    @app.get("/api/ready")
    def readiness():
        try:
            with engine.connect() as connection:
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if revision != "9e57ab896061":
                    return JSONResponse(status_code=503, content={"status": "not_ready"}, headers={"Cache-Control": "no-store"})
                connection.execute(text("SELECT 1 FROM departments LIMIT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready"}, headers={"Cache-Control": "no-store"})
        return JSONResponse(content={"status": "ready"}, headers={"Cache-Control": "no-store"})

    app.include_router(router)
    app.include_router(scheduling_router)
    app.include_router(workflows_router)
    app.include_router(attendance_router)
    return app


app = create_app()
