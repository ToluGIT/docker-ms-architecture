"""
User repository with traced database operations
"""
from sqlalchemy.orm import Session
from ..models import User
from typing import List, Optional
from ..db_tracing import traced_db_operation

class UserRepository:
    """Repository for User entity with traced database operations"""
    
    @staticmethod
    @traced_db_operation("get_users_list")
    def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Get a list of users with tracing"""
        return db.query(User).offset(skip).limit(limit).all()
    
    @staticmethod
    @traced_db_operation("get_user_by_id")
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get a single user by ID with tracing"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    @traced_db_operation("get_user_by_username")
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get a user by username with tracing"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    @traced_db_operation("get_user_by_email")
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get a user by email with tracing"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    @traced_db_operation("create_user")
    def create_user(db: Session, user_data: dict) -> User:
        """Create a new user with tracing"""
        db_user = User(**user_data)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    @traced_db_operation("update_user")
    def update_user(db: Session, user_id: int, user_data: dict) -> Optional[User]:
        """Update a user with tracing"""
        db_user = UserRepository.get_user_by_id(db, user_id)
        if not db_user:
            return None
            
        for key, value in user_data.items():
            if hasattr(db_user, key):
                setattr(db_user, key, value)
                
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    @traced_db_operation("delete_user")
    def delete_user(db: Session, user_id: int) -> bool:
        """Delete a user with tracing"""
        db_user = UserRepository.get_user_by_id(db, user_id)
        if not db_user:
            return False
            
        db.delete(db_user)
        db.commit()
        return True
