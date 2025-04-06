"""
Cached repository implementation using Redis
"""
import json
import logging
import time
import functools
from typing import Optional, Any, Type, List, TypeVar, Generic, Dict, Callable
from sqlalchemy.orm import Session
from ..models import Base

# Try to import Redis and tracing modules, handle gracefully if not available
try:
    import redis
    from ..cache_tracing import TracedRedis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from opentelemetry import trace
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Generic type for SQLAlchemy models
T = TypeVar('T', bound=Base)

def traced_operation(name: str) -> Callable:
    """Decorator for tracing repository operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not TRACING_AVAILABLE:
                return func(self, *args, **kwargs)
            
            tracer = trace.get_tracer(__name__)
            
            attributes = {
                "repository.model": self.model_class.__name__,
                "repository.operation": name,
                "repository.cached": True,
                "repository.cache_prefix": self.prefix
            }
            
            db = self._find_db_arg(*args, **kwargs)
            if db:
                attributes["repository.db_session_id"] = id(db)
            
            with tracer.start_as_current_span(
                f"cache_repo.{name}",
                attributes=attributes
            ) as span:
                start_time = time.time()
                
                try:
                    result = func(self, *args, **kwargs)
                    
                    if span and hasattr(span, 'set_attribute'):
                        span.set_attribute("status", "success")
                        
                        if isinstance(result, list):
                            span.set_attribute("repository.result_count", len(result))
                        elif name.startswith("get_") and name != "get_all":
                            span.set_attribute("repository.result_found", result is not None)
                    
                    return result
                except Exception as e:
                    if span and hasattr(span, 'set_status'):
                        span.set_status(trace.Status(trace.StatusCode.ERROR))
                        span.record_exception(e)
                        span.set_attribute("error.type", e.__class__.__name__)
                        span.set_attribute("error.message", str(e))
                    raise
                finally:
                    if span and hasattr(span, 'set_attribute'):
                        execution_time = (time.time() - start_time) * 1000
                        span.set_attribute("repository.execution_time_ms", execution_time)
        return wrapper
    return decorator

class CachedRepository(Generic[T]):
    """Repository with Redis caching and tracing capabilities"""

    def __init__(self, model_class: Type[T], prefix: str = None, redis_client = None, ttl: int = 3600):
        """Initialize the cached repository"""
        self.model_class = model_class
        self.prefix = prefix or model_class.__name__.lower()
        self.ttl = ttl
        self.redis = None
        
        if REDIS_AVAILABLE and redis_client:
            if hasattr(redis_client, '_trace_operation'):
                self.redis = redis_client
            else:
                self.redis = TracedRedis.from_client(redis_client)
            logger.info(f"Cached repository initialized for {model_class.__name__} with TTL {ttl}s")
        else:
            logger.warning(f"Redis not available, {model_class.__name__} repository will not use caching")

    def _cache_key(self, identifier: Any) -> str:
        """Generate a cache key for an entity"""
        return f"{self.prefix}:{identifier}"
    
    def _serialize(self, obj: T) -> str:
        """Serialize an entity for caching"""
        if obj is None:
            return None
            
        if hasattr(obj, '__table__'):
            data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            for key, value in data.items():
                if hasattr(value, 'isoformat'):
                    data[key] = value.isoformat()
            return json.dumps(data)
        return json.dumps(obj)
    
    def _deserialize(self, data: str) -> Optional[Dict[str, Any]]:
        """Deserialize cached data"""
        if not data:
            return None
        try:
            return json.loads(data)
        except Exception as e:
            logger.error(f"Error deserializing data: {e}")
            return None
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Optional[T]:
        """Create an entity instance from a dictionary"""
        if not data:
            return None
        try:
            instance = self.model_class()
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            return instance
        except Exception as e:
            logger.error(f"Error creating entity from dict: {e}")
            return None
    
    def _find_db_arg(self, *args, **kwargs) -> Optional[Session]:
        """Find the database session in args or kwargs"""
        for arg in args:
            if isinstance(arg, Session):
                return arg
        for value in kwargs.values():
            if isinstance(value, Session):
                return value
        return None

    @traced_operation("get_by_id")
    def get_by_id(self, db: Session, id: Any) -> Optional[T]:
        """Get an entity by ID with caching"""
        if not self.redis:
            return db.query(self.model_class).filter_by(id=id).first()
        
        cache_key = self._cache_key(id)
        cached_data = self.redis.get(cache_key)
        if cached_data:
            data = self._deserialize(cached_data)
            entity = self._entity_from_dict(data)
            if entity:
                return entity
        
        entity = db.query(self.model_class).filter_by(id=id).first()
        if entity:
            serialized = self._serialize(entity)
            self.redis.setex(cache_key, self.ttl, serialized)
        
        return entity

    @traced_operation("get_all")
    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination"""
        return db.query(self.model_class).offset(skip).limit(limit).all()
    
    @traced_operation("create")
    def create(self, db: Session, data: Dict[str, Any]) -> T:
        """Create a new entity"""
        entity = self.model_class(**data)
        db.add(entity)
        db.commit()
        db.refresh(entity)
        
        if self.redis and entity:
            cache_key = self._cache_key(entity.id)
            serialized = self._serialize(entity)
            self.redis.setex(cache_key, self.ttl, serialized)
        
        return entity
    
    @traced_operation("update")
    def update(self, db: Session, id: Any, data: Dict[str, Any]) -> Optional[T]:
        """Update an entity"""
        entity = db.query(self.model_class).filter_by(id=id).first()
        if not entity:
            return None
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        
        db.commit()
        db.refresh(entity)
        
        if self.redis:
            cache_key = self._cache_key(id)
            serialized = self._serialize(entity)
            self.redis.setex(cache_key, self.ttl, serialized)
        
        return entity
    
    @traced_operation("delete")
    def delete(self, db: Session, id: Any) -> bool:
        """Delete an entity"""
        entity = db.query(self.model_class).filter_by(id=id).first()
        if not entity:
            return False
        
        db.delete(entity)
        db.commit()
        
        if self.redis:
            cache_key = self._cache_key(id)
            self.redis.delete(cache_key)
        
        return True
    
    @traced_operation("invalidate_cache")
    def invalidate_cache(self, id: Any) -> bool:
        """Invalidate cache for an entity"""
        if not self.redis:
            return False
        
        cache_key = self._cache_key(id)
        return bool(self.redis.delete(cache_key))
