from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginInput
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def authenticate_user(email: str, password: str, db: Session) -> User:
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return user


@router.post("/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    """JSON login for apps and API clients."""
    user = authenticate_user(payload.email, payload.password, db)
    return {"access_token": create_access_token(user), "token_type": "bearer"}


@router.post("/token")
def oauth_token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 form login used by Swagger's Authorize button."""
    user = authenticate_user(form.username, form.password, db)
    return {"access_token": create_access_token(user), "token_type": "bearer"}
