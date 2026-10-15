"""CampusShift's local API. No cloud services are required."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="CampusShift API", version="0.1.0")
    origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.get("/")
    def welcome() -> dict[str, str]:
        return {"message": "Welcome to CampusShift!"}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "application": "CampusShift"}

    return app


app = create_app()
