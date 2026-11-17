import bcrypt
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config.settings import settings


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def create_access_token(
    user_id: int,
    role: str
) -> str:

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def sign_filename(filename: str) -> str:
    """HMAC signature for upload filenames served without auth.

    <img> tags can't send Authorization headers, so privacy-sensitive
    uploads (proctoring snapshots) carry an HMAC query param instead.
    """
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        filename.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def verify_filename_sig(filename: str, sig: str) -> bool:
    """Constant-time check of a signature produced by sign_filename."""
    if not sig:
        return False
    return hmac.compare_digest(sign_filename(filename), sig)