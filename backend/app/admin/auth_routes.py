from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.schemas import AdminLoginRequest, AdminLoginResponse, AdminMeResponse
from app.core.database import get_db
from app.core.rate_limit import check_rate_limit
from app.core.security import create_admin_access_token, get_current_admin, verify_password
from app.models import User

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

ADMIN_LOGIN_MAX_ATTEMPTS = 3
ADMIN_LOGIN_WINDOW_SECONDS = 15 * 60


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(f"admin-login:{payload.email}", ADMIN_LOGIN_MAX_ATTEMPTS, ADMIN_LOGIN_WINDOW_SECONDS)

    ip = request.client.host if request.client else None
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not user.is_admin or not verify_password(payload.password, user.password_hash):
        # Generic failure — never reveal whether the email exists or belongs to an admin.
        if user:
            log_admin_action(db, user.id, "admin.login_failed", ip_address=ip)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    access_token = create_admin_access_token(user.id, user.email)
    log_admin_action(db, user.id, "admin.login_success", ip_address=ip)
    db.commit()

    return AdminLoginResponse(access_token=access_token, name=user.name, email=user.email, admin_role=user.admin_role)


@router.get("/me", response_model=AdminMeResponse)
def admin_me(admin: User = Depends(get_current_admin)):
    return AdminMeResponse(id=admin.id, name=admin.name, email=admin.email, admin_role=admin.admin_role)
