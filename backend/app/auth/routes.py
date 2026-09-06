from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.schemas import (
    ForgotPasswordRequest,
    GenericMessageResponse,
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    VerifyEmailResponse,
)
from app.core.database import get_db
from app.core.email import send_password_reset_email, send_verification_email
from app.core.rate_limit import check_rate_limit
from app.core.time_utils import is_expired
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_token,
    hash_password,
    verify_password,
)
from app.models import AuthToken, AuthTokenType, User

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_SIGNUP_MESSAGE = "If that email is available, we've sent a verification link. Please check your inbox."
GENERIC_FORGOT_PASSWORD_MESSAGE = "If that email exists, we've sent a password reset link."
REFRESH_COOKIE_NAME = "refresh_token"


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        # Don't leak whether the email already exists — return the same generic message.
        return SignupResponse(message=GENERIC_SIGNUP_MESSAGE)

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        # Auto-verified: email delivery only works for the Resend account owner's own
        # address until a custom domain is verified at resend.com/domains (sandbox mode
        # restriction), so gating login on a link that most users could never receive
        # would lock everyone else out. Revert to False here once a verified sending
        # domain is configured, and re-enable the is_verified check in login() below.
        is_verified=True,
    )
    db.add(user)
    db.flush()

    token_value = generate_token()
    auth_token = AuthToken(
        user_id=user.id,
        token=token_value,
        type=AuthTokenType.verify_email,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(auth_token)
    db.commit()

    send_verification_email(user.email, token_value)

    return SignupResponse(message=GENERIC_SIGNUP_MESSAGE)


@router.get("/verify-email", response_model=VerifyEmailResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    auth_token = (
        db.query(AuthToken)
        .filter(AuthToken.token == token, AuthToken.type == AuthTokenType.verify_email)
        .first()
    )

    if not auth_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link.")
    if auth_token.used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link has already been used.")
    if is_expired(auth_token.expires_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link has expired.")

    user = db.query(User).filter(User.id == auth_token.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link.")

    user.is_verified = True
    auth_token.used = True
    db.commit()

    return VerifyEmailResponse(message="Email verified! You can now log in.")


@router.post("/resend-verification", response_model=GenericMessageResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    check_rate_limit(f"resend-verification:{payload.email}")

    user = db.query(User).filter(User.email == payload.email).first()
    if user and not user.is_verified:
        token_value = generate_token()
        auth_token = AuthToken(
            user_id=user.id,
            token=token_value,
            type=AuthTokenType.verify_email,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(auth_token)
        db.commit()
        send_verification_email(user.email, token_value)

    return GenericMessageResponse(message=GENERIC_SIGNUP_MESSAGE)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    check_rate_limit(f"login:{payload.email}")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked. Contact support if you believe this is an error.",
        )

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/auth",
    )

    return LoginResponse(access_token=access_token)


@router.post("/refresh-token", response_model=RefreshResponse)
def refresh_token(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided.")

    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return RefreshResponse(access_token=create_access_token(user.id, user.email))


@router.post("/forgot-password", response_model=GenericMessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    check_rate_limit(f"forgot-password:{payload.email}")

    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token_value = generate_token()
        auth_token = AuthToken(
            user_id=user.id,
            token=token_value,
            type=AuthTokenType.reset_password,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db.add(auth_token)
        db.commit()
        send_password_reset_email(user.email, token_value)

    # Always return the same message, whether or not the email exists.
    return GenericMessageResponse(message=GENERIC_FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=GenericMessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_token = (
        db.query(AuthToken)
        .filter(AuthToken.token == payload.token, AuthToken.type == AuthTokenType.reset_password)
        .first()
    )

    if not auth_token or auth_token.used or is_expired(auth_token.expires_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.")

    user = db.query(User).filter(User.id == auth_token.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.")

    user.password_hash = hash_password(payload.new_password)
    auth_token.used = True
    db.commit()

    return GenericMessageResponse(message="Password reset successfully. You can now log in.")
