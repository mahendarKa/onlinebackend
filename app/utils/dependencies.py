from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.models.user import User


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user = (
        db.query(User)
        .filter(User.id == int(user_id))
        .first()
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


def require_role(*allowed_roles):

    # superadmin inherits every permission granted to admin.
    effective_roles = set(allowed_roles)
    if "admin" in effective_roles:
        effective_roles.add("superadmin")

    def role_checker(
        current_user: User = Depends(get_current_user)
    ):

        if current_user.role not in effective_roles:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )

        return current_user

    return role_checker


def question_edit_guard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Router-level guard for question write endpoints.

    Any POST/PUT/PATCH/DELETE carrying a ``question_id`` path param is
    rejected while the question is locked (its exam has attempts) or
    frozen (a change request is pending admin approval).
    """
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    question_id = request.path_params.get("question_id")
    if question_id is None:
        return

    # Deferred import — services pull in models that depend on this file
    # only indirectly, but keeping it local avoids import cycles.
    from app.services.question_change import ensure_question_editable

    ensure_question_editable(db, int(question_id), current_user)