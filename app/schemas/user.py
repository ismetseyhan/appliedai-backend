from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None


class UserCreate(BaseModel):
    """Schema for user registration (extracted from Firebase token)"""
    pass


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TokenData(BaseModel):
    """Decoded Firebase token data"""
    uid: str
    email: str
    name: Optional[str] = None
