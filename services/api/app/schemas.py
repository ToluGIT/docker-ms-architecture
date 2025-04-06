from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    username: str
    email: str  # Using str since EmailStr might require additional dependencies

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)  # Enforce password length

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        # Note: hashed_password is intentionally not included in the response