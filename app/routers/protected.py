from fastapi import APIRouter, Depends

from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    require_role
)


router = APIRouter(
    prefix="/api/test",
    tags=["Authentication Test"]
)


@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user)
):

    return {
        "message": "JWT authentication successful",
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    }


@router.get("/student")
def student_test(
    current_user: User = Depends(
        require_role("student")
    )
):

    return {
        "message": "Student access successful",
        "user": current_user.name
    }


@router.get("/teacher")
def teacher_test(
    current_user: User = Depends(
        require_role("teacher")
    )
):

    return {
        "message": "Teacher access successful",
        "user": current_user.name
    }


@router.get("/admin")
def admin_test(
    current_user: User = Depends(
        require_role("admin")
    )
):

    return {
        "message": "Admin access successful",
        "user": current_user.name
    }