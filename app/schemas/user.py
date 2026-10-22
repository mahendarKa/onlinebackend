from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, EmailStr, Field


def _validate_mobile(v: Optional[str]) -> Optional[str]:
    """Mobile is optional, but when given it must be exactly 10 digits."""
    if v is None:
        return v
    digits = sum(c.isdigit() for c in v)
    if digits == 0:
        return None  # treat blank/non-numeric-empty input as unset
    if digits != 10:
        raise ValueError("Mobile number must be exactly 10 digits")
    return v


MobileStr = Annotated[str, AfterValidator(_validate_mobile)]


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
    mobile_number: Optional[MobileStr] = Field(
        default=None, max_length=20
    )


class AdminUserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
    role: str
    mobile_number: Optional[MobileStr] = Field(
        default=None, max_length=20
    )
    profile_pic: Optional[str] = Field(default=None, max_length=500)


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(
        default=None, min_length=1, max_length=100
    )
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=6)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    mobile_number: Optional[MobileStr] = Field(
        default=None, max_length=20
    )
    profile_pic: Optional[str] = Field(default=None, max_length=500)


class UserResponse(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: str
    email: str
    role: str
    is_active: bool
    mobile_number: Optional[str] = None
    profile_pic: Optional[str] = None

    class Config:
        from_attributes = True