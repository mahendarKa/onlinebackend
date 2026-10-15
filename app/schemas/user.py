from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
    mobile_number: Optional[str] = Field(default=None, max_length=20)


class AdminUserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
    role: str
    mobile_number: Optional[str] = Field(default=None, max_length=20)
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
    mobile_number: Optional[str] = Field(default=None, max_length=20)
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