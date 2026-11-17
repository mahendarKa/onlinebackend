from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.activity_service import log_audit
from app.utils.rate_limit import RateLimiter
from app.utils.security import (
    verify_password,
    create_access_token
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

# Brute-force protection: 5 attempts/min per email, 20/min per IP.
# Two keys so a password spray across many accounts from one address
# is still capped at the IP level.
_email_limiter = RateLimiter(max_hits=5, window_seconds=60)
_ip_limiter = RateLimiter(max_hits=20, window_seconds=60)

# Single failure response for every rejection path so callers cannot
# enumerate accounts via status code or message differences.
_INVALID = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password"
)


@router.post(
    "/login",
    response_model=LoginResponse
)
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):

    client_ip = request.client.host if request.client else "unknown"
    email_key = login_data.email.lower().strip()

    if (
        not _ip_limiter.check(client_ip)
        or not _email_limiter.check(email_key)
    ):
        retry = max(
            _ip_limiter.retry_after(client_ip),
            _email_limiter.retry_after(email_key),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {retry}s.",
            headers={"Retry-After": str(retry)},
        )

    user = (
        db.query(User)
        .filter(User.email == login_data.email)
        .first()
    )

    # Unknown user OR inactive account OR wrong password -> identical
    # 401, so no signal distinguishes "account exists but disabled".
    if (
        user is None
        or not user.is_active
        or not verify_password(login_data.password, user.password)
    ):
        raise _INVALID

    access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )

    log_audit(
        db, user.id, "auth.login", "user", user.id,
        details=f"{user.email} logged in",
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "mobile_number": user.mobile_number,
        "profile_pic": user.profile_pic,
    }