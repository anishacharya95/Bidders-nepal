from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user: User, expires_minutes: int | None = None):
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_exp_minutes
    )
    return jwt.encode(
        {"sub": str(user.id), "role": user.role, "exp": expires},
        settings.jwt_secret,
        algorithm="HS256",
    )


def _decode(token: str, db: Session) -> User:
    unauthorized = HTTPException(status_code=401, detail="Invalid authentication credentials")
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError, TypeError):
        raise unauthorized
    user = db.get(User, user_id)
    if not user or not user.is_active or user.role != "admin":
        raise unauthorized
    return user


def get_current_admin(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode(token, db)


def get_admin_from_cookie(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.admin_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode(token, db)


def set_admin_cookie(response: Response, user: User) -> str:
    token = create_access_token(
        user, expires_minutes=settings.admin_session_minutes
    )
    response.set_cookie(
        settings.admin_cookie_name,
        token,
        max_age=settings.admin_session_minutes * 60,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="lax",
        path="/",
    )
    return token


def clear_admin_cookie(response: Response) -> None:
    response.delete_cookie(settings.admin_cookie_name, path="/")
