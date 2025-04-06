"""
Cached User repository implementation
"""
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from ..models import User
from .cached_repository import CachedRepository, traced_operation

class CachedUserRepository(CachedRepository[User]):
    """User repository with Redis caching"""
    
    def __init__(self, redis_client=None, ttl=3600):
        """Initialize with User model and 'user' prefix"""
        super().__init__(User, prefix="user", redis_client=redis_client, ttl=ttl)
    
    @traced_operation("get_by_username")
    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Get a user by username
        
        Args:
            db: Database session
            username: Username to look up
            
        Returns:
            User: User if found, None otherwise
        """
        # This is a common query that benefits from caching
        # Generate cache key
        cache_key = f"{self.prefix}:username:{username}"
        
        # Try to get from cache if Redis is available
        if self.redis:
            # Check cache first
            cached_data = self.redis.get(cache_key)
            if cached_data:
                # We found username in cache, now deserialize
                data = self._deserialize(cached_data)
                if data and 'id' in data:
                    # This is just a reference to the main user record
                    # Now get the complete user from the main cache
                    return self.get_by_id(db, data['id'])
        
        # Not in cache, query database
        user = db.query(User).filter(User.username == username).first()
        
        # Store in cache if found and Redis is available
        if user and self.redis:
            # Store main user record
            self.get_by_id(db, user.id)  # This will cache the user object
            
            # Store username lookup
            lookup = {'id': user.id}
            self.redis.setex(cache_key, self.ttl, self._serialize(lookup))
        
        return user
    
    @traced_operation("get_by_email")
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Get a user by email
        
        Args:
            db: Database session
            email: Email to look up
            
        Returns:
            User: User if found, None otherwise
        """
        # Similar to username lookup, with different cache key
        cache_key = f"{self.prefix}:email:{email}"
        
        # Try to get from cache if Redis is available
        if self.redis:
            # Check cache first
            cached_data = self.redis.get(cache_key)
            if cached_data:
                # We found email in cache, now deserialize
                data = self._deserialize(cached_data)
                if data and 'id' in data:
                    # This is just a reference to the main user record
                    # Now get the complete user from the main cache
                    return self.get_by_id(db, data['id'])
        
        # Not in cache, query database
        user = db.query(User).filter(User.email == email).first()
        
        # Store in cache if found and Redis is available
        if user and self.redis:
            # Store main user record
            self.get_by_id(db, user.id)  # This will cache the user object
            
            # Store email lookup
            lookup = {'id': user.id}
            self.redis.setex(cache_key, self.ttl, self._serialize(lookup))
        
        return user
