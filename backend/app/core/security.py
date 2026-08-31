import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User


def _user_from_access_token(token: str, db: Session) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked. Contact support if you believe this is an error.",
        )
    return user

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    payload = decode_token(credentials.credentials)
    if payload.get("type") not in ("access", "impersonation"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    # Checked first and unconditionally (including under impersonation) — a blocked
    # user must stay blocked no matter which token type is used to reach them.
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked. Contact support if you believe this is an error.",
        )

    return user


def is_impersonating(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str | None:
    """Returns the impersonating admin's user id if this request is using an
    impersonation token, else None. Use as a guard on mutating routes that should be
    blocked while an admin is viewing the app as another user."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return None
    if payload.get("type") == "impersonation":
        return payload.get("admin_id")
    return None


def block_if_impersonating(admin_id: str | None = Depends(is_impersonating)) -> None:
    """Dependency to add to mutating routes (send message, delete document, etc.) that
    should not be usable while an admin is impersonating a user — impersonation is for
    read-only debugging, not taking actions as the user."""
    if admin_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is disabled while viewing the app in impersonation mode.",
        )


# ---- Admin auth ----


def create_admin_access_token(user_id: uuid.UUID, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire, "type": "admin_access"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_impersonation_token(target_user_id: uuid.UUID, target_email: str, admin_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "sub": str(target_user_id),
        "email": target_email,
        "exp": expire,
        "type": "impersonation",
        "admin_id": str(admin_id),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Auth dependency for every /admin/* route — separate token type from regular user
    access tokens, so a leaked/reused normal session token can never reach admin routes
    and vice versa."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    if payload.get("type") != "admin_access":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    return user


def require_role(*allowed_roles: str):
    def dependency(admin: User = Depends(get_current_admin)) -> User:
        if admin.admin_role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this action.")
        return admin

    return dependency


def get_current_user_media(
    token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Same as get_current_user, but also accepts the access token as a `?token=` query
    param — needed because <audio>/<video> elements can't send a custom Authorization
    header, so the frontend passes the token in the media URL instead."""
    if token:
        return _user_from_access_token(token, db)
    if credentials is not None:
        return _user_from_access_token(credentials.credentials, db)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
