"""API Gateway HTTP API v2 -> existing FastAPI routes/authentication.

The adapter is cached across warm invocations; NullPool closes each request's
connections. No migrations, seed, AWS SDK or secret lookups run on request paths.
"""
from functools import lru_cache
from mangum import Mangum


def make_handler(app):
    return Mangum(app, lifespan="off")


@lru_cache(maxsize=1)
def adapter():
    from app.core.lambda_runtime import prepare_environment
    try:
        prepare_environment()
        from main import app
    except Exception:
        # Never expose an environment value or exception payload on cold start.
        raise RuntimeError("CampusShift Lambda configuration failed") from None
    return make_handler(app)


def handler(event, context):
    return adapter()(event, context)
