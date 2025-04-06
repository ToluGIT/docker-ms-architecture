from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi.util import get_remote_address
from typing import List, Optional
import time
from .. import models, database
from pydantic import BaseModel, EmailStr, Field
from app.config import limiter
from ..auth import get_current_user
from ..trace_metrics import track_request_for_slo

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=8) 

class UserResponse(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

# Repository integration
try:
    from ..repositories.user_repository import UserRepository
    repository_available = True
except ImportError:
    repository_available = False

# Helper functions
def get_user_by_email(db: Session, email: str):
    if repository_available:
        return UserRepository.get_user_by_email(db, email)
    else:
        return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    if repository_available:
        return UserRepository.get_user_by_username(db, username)
    else:
        return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(db: Session, user_id: int):
    if repository_available:
        return UserRepository.get_user_by_id(db, user_id)
    else:
        return db.query(models.User).filter(models.User.id == user_id).first()

def create_user(db: Session, user: UserCreate):
    if repository_available:
        # In a real application, hash the password
        hashed_password = models.User.get_password_hash(user.password)
        user_data = user.dict()
        user_data["hashed_password"] = hashed_password
        del user_data["password"]
        return UserRepository.create_user(db, user_data)
    else:
        # Original implementation
        hashed_password = models.User.get_password_hash(user.password)
        db_user = models.User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

# Endpoints with SLO tracking
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_new_user(request: Request, user: UserCreate, db: Session = Depends(database.get_db)):
    """Create a new user with SLO tracking"""
    start_time = time.time()
    is_error = False
    
    try:
        # Check if email already exists
        db_user = get_user_by_email(db, email=user.email)
        if db_user:
            is_error = True
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Check if username already exists
        db_user = get_user_by_username(db, username=user.username)
        if db_user:
            is_error = True
            raise HTTPException(
                status_code=400,
                detail="Username already taken"
            )
        
        # Create the user
        result = create_user(db=db, user=user)
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="create_user",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return result
    except Exception as e:
        # Track error for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="create_user",
            slo_name="data_access",
            latency=duration,
            is_error=True
        )
        raise

@router.get("/", response_model=List[UserResponse])
@limiter.limit("30/minute")
def read_users(
    request: Request, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all users with SLO tracking"""
    start_time = time.time()
    
    try:
        # Get users from database
        users = db.query(models.User).offset(skip).limit(limit).all()
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="read_users",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return users
    except Exception as e:
        # Track error for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="read_users",
            slo_name="data_access",
            latency=duration,
            is_error=True
        )
        raise

@router.get("/{user_id}", response_model=UserResponse)
@limiter.limit("30/minute")
def read_user(request: Request, user_id: int, db: Session = Depends(database.get_db)):
    """Get a specific user by ID with SLO tracking"""
    start_time = time.time()
    
    try:
        # Get user from database
        db_user = get_user_by_id(db, user_id=user_id)
        if db_user is None:
            # Track error for SLO
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="read_user",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
            raise HTTPException(status_code=404, detail="User not found")
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="read_user",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return db_user
    except Exception as e:
        # Only track here if it's not already tracked above
        if not isinstance(e, HTTPException) or e.status_code != 404:
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="read_user",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
        raise
