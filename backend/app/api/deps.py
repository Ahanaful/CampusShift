import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import require_secret
from app.models import User
from app.db.transactions import reserve_write

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    with request.app.state.session_factory() as session:
        # Acquire before authentication loads ORM objects, avoiding stale state
        # while waiting for another worker's invariant-changing transaction.
        if session.get_bind().dialect.name == "postgresql" and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            reserve_write(session)
        yield session


def current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    settings = request.app.state.settings
    require_secret(settings)
    unauthorized = HTTPException(401, "Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    if not credentials:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"],
                             issuer="campusshift", audience="campusshift-web",
                             options={"require": ["sub", "exp", "iat"]})
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise unauthorized from None
    user = db.get(User, user_id)
    if not user:
        raise unauthorized
    return user


def student_only(user: User = Depends(current_user)):
    if user.role != "student":
        raise HTTPException(403, "Student access required.")
    return user


def supervisor_only(user: User = Depends(current_user)):
    if user.role != "supervisor":
        raise HTTPException(403, "Supervisor access required.")
    return user
