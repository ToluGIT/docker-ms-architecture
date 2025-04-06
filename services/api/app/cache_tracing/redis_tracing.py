"""
Enhanced Redis tracing for OpenTelemetry
"""
import functools
import time
import logging
import json
from typing import Optional, Callable, Dict, Any, Union, List
from contextlib import contextmanager

# Try to import OpenTelemetry and Redis, handle gracefully if not available
try:
    import redis
    from redis.client import Redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.trace.status import Status, StatusCode
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cache operation statistics
cache_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
    "errors": 0,
    "total_time_ms": 0,
    "operations": 0
}

def instrument_redis(client=None):
    """
    Wrap an existing Redis client with tracing or return a new traced client
    
    Args:
        client: Existing Redis client to wrap (optional)
    
    Returns:
        TracedRedis: A Redis client with tracing capabilities
    """
    if not REDIS_AVAILABLE:
        logger.warning("Redis package not available")
        return None
    
    if client is None:
        logger.info("No Redis client provided, returning a new traced client")
        return TracedRedis()
    
    if isinstance(client, TracedRedis):
        logger.info("Client is already traced")
        return client
    
    logger.info("Wrapping Redis client with tracing")
    return TracedRedis.from_client(client)

class TracedRedis:
    """
    Redis client wrapper with integrated tracing
    """
    def __init__(self, host='localhost', port=6379, db=0, password=None, **kwargs):
        """
        Initialize a traced Redis client
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            **kwargs: Additional arguments for Redis client
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis package not available")
        
        self._redis = redis.Redis(host=host, port=port, db=db, password=password, **kwargs)
        self._connection_info = f"redis://{host}:{port}/{db}"
    
    @classmethod
    def from_client(cls, client):
        """
        Create a traced Redis client from an existing client
        
        Args:
            client: Existing Redis client
            
        Returns:
            TracedRedis: A traced Redis client
        """
        traced = cls()
        traced._redis = client
        connection_params = client.connection_pool.connection_kwargs
        traced._connection_info = (
            f"redis://{connection_params.get('host', 'localhost')}:"
            f"{connection_params.get('port', 6379)}/"
            f"{connection_params.get('db', 0)}"
        )
        return traced
    
    @classmethod
    def from_url(cls, url, **kwargs):
        """
        Create a traced Redis client from a URL
        
        Args:
            url: Redis URL
            **kwargs: Additional arguments for Redis client
            
        Returns:
            TracedRedis: A traced Redis client
        """
        client = redis.Redis.from_url(url, **kwargs)
        traced = cls.from_client(client)
        traced._connection_info = url
        return traced
    
    def _trace_operation(self, operation, key=None, args=None, value_hint=None):
        """
        Internal method to trace a Redis operation
        
        Args:
            operation: Name of the Redis operation
            key: The Redis key (optional)
            args: Additional arguments for the span (optional)
            value_hint: Hint about the value type or format (optional)
            
        Returns:
            A context manager for the trace span
        """
        if not TRACING_AVAILABLE:
            # Return a dummy context manager if tracing is not available
            @contextmanager
            def dummy_context():
                yield None
            return dummy_context()
        
        tracer = trace.get_tracer(__name__)
        
        # Prepare span attributes
        span_attributes = {
            "db.system": "redis",
            "db.operation": operation,
            "db.redis.connection": self._connection_info
        }
        
        if key is not None:
            # Truncate long keys to avoid span attribute size limits
            if isinstance(key, str) and len(key) > 128:
                key_display = key[:128] + "..."
            else:
                key_display = str(key)
                
            span_attributes["db.redis.key"] = key_display
        
        if args:
            span_attributes.update(args)
            
        if value_hint:
            span_attributes["db.redis.value_hint"] = value_hint
            
        # Create and return the span context
        return tracer.start_as_current_span(
            f"redis.{operation}",
            attributes=span_attributes
        )
    @classmethod     
    def _traced_operation(cls, operation):
        """
        Create a decorator to trace a Redis operation
        
        Args:
            operation: Name of the Redis operation
            
        Returns:
            A decorator function
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                # The first argument after self is usually the key
                key = args[1] if len(args) > 1 else None
                
                # For multi-key operations, handle differently
                if operation in ['mget', 'mset'] and isinstance(key, (list, tuple)):
                    # For multi-key operations, join keys for display
                    keys_display = ', '.join(str(k) for k in key[:5])
                    if len(key) > 5:
                        keys_display += f"... ({len(key)} total)"
                    key = keys_display
                
                span_args = {}
                
                # Add specialized attributes based on the operation
                if operation == 'get':
                    span_args["db.redis.operation_type"] = "read"
                elif operation in ['set', 'setex']:
                    span_args["db.redis.operation_type"] = "write"
                    # Add TTL information if available
                    if operation == 'setex' and len(args) > 2:
                        span_args["db.redis.ttl"] = args[2]
                elif operation == 'delete':
                    span_args["db.redis.operation_type"] = "delete"
                
                # Track this operation in stats
                cache_stats["operations"] += 1
                
                # Start the span
                with self._trace_operation(operation, key, span_args) as span:
                    try:
                        # Execute the original Redis operation
                        result = func(*args, **kwargs)
                        
                        # Update cache stats based on the operation
                        if operation == 'get':
                            if result is None:
                                cache_stats["misses"] += 1
                                span_args["db.redis.hit"] = False
                            else:
                                cache_stats["hits"] += 1
                                span_args["db.redis.hit"] = True
                        elif operation in ['set', 'setex']:
                            cache_stats["sets"] += 1
                        elif operation == 'delete':
                            cache_stats["deletes"] += 1
                        
                        # Record success and result info in the span
                        if span and hasattr(span, 'set_attribute'):
                            if operation == 'get' and result is not None:
                                # For get operations with a result, add result type and length
                                try:
                                    span.set_attribute("db.redis.result_type", type(result).__name__)
                                    if isinstance(result, bytes):
                                        span.set_attribute("db.redis.result_length_bytes", len(result))
                                except Exception:
                                    pass
                            
                            # Add cache hit/miss attribute for get operations
                            if operation == 'get':
                                span.set_attribute("db.redis.hit", result is not None)
                        
                        return result
                        
                    except RedisError as e:
                        # Record the error
                        cache_stats["errors"] += 1
                        
                        if span and hasattr(span, 'set_status'):
                            span.set_status(Status(StatusCode.ERROR))
                            span.record_exception(e)
                            span.set_attribute("error.type", e.__class__.__name__)
                            span.set_attribute("error.message", str(e))
                        
                        # Re-raise the exception
                        raise
                    finally:
                        # Record timing information
                        duration_ms = (time.time() - start_time) * 1000
                        cache_stats["total_time_ms"] += duration_ms
                        
                        if span and hasattr(span, 'set_attribute'):
                            span.set_attribute("db.execution_time_ms", duration_ms)
            
            return wrapper
        
        return decorator
    
    def __getattr__(self, name):
        """
        Proxy attribute access to the underlying Redis client, adding tracing
        
        This allows us to transparently add tracing to any Redis operation.
        """
        redis_attr = getattr(self._redis, name)
        
        # If this is a callable (method), add tracing
        if callable(redis_attr):
            return self._traced_operation(name)(redis_attr)
        
        # Otherwise just return the attribute
        return redis_attr
    
    # Explicitly implement core Redis methods for better IDE support
    @property
    def connection_pool(self):
        return self._redis.connection_pool
    
    def get(self, key):
        return self._redis.get(key)
    
    def set(self, key, value, ex=None, px=None, nx=False, xx=False):
        return self._redis.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
    
    def setex(self, key, time, value):
        return self._redis.setex(key, time, value)
    
    def delete(self, *keys):
        return self._redis.delete(*keys)
    
    def exists(self, *keys):
        return self._redis.exists(*keys)
    
    def expire(self, key, time):
        return self._redis.expire(key, time)
    
    def ttl(self, key):
        return self._redis.ttl(key)
    
    def incr(self, key, amount=1):
        return self._redis.incr(key, amount)
    
    def decr(self, key, amount=1):
        return self._redis.decr(key, amount)
    
    def hget(self, key, field):
        return self._redis.hget(key, field)
    
    def hset(self, key, field, value):
        return self._redis.hset(key, field, value)
    
    def hmget(self, key, fields):
        return self._redis.hmget(key, fields)
    
    def hmset(self, key, mapping):
        return self._redis.hmset(key, mapping)
    
    def hgetall(self, key):
        return self._redis.hgetall(key)
    
    def lpush(self, key, *values):
        return self._redis.lpush(key, *values)
    
    def rpush(self, key, *values):
        return self._redis.rpush(key, *values)
    
    def lpop(self, key):
        return self._redis.lpop(key)
    
    def rpop(self, key):
        return self._redis.rpop(key)
    
    def lrange(self, key, start, end):
        return self._redis.lrange(key, start, end)
    
    def ping(self):
        return self._redis.ping()

    """Get the current cache statistics"""
    # Calculate average operation time
    if cache_stats["operations"] > 0:
        avg_time = cache_stats["total_time_ms"] / cache_stats["operations"]
    else:
        avg_time = 0
        
    # Return stats with calculated values

def get_cache_stats():
    if cache_stats["operations"] > 0:
        avg_time = (cache_stats["total_time_ns"] / 1e6) / cache_stats["operations"]
    else:
        avg_time = 0
    
    return {
        "hit_ratio": cache_stats["hits"] / (cache_stats["hits"] + cache_stats["misses"]) * 100 if (cache_stats["hits"] + cache_stats["misses"]) > 0 else 0,
        "avg_operation_time_ms": avg_time,
        "operations": cache_stats["operations"],
        "hits": cache_stats["hits"],
        "misses": cache_stats["misses"],
        "sets": cache_stats["sets"],
        "deletes": cache_stats["deletes"],
        "errors": cache_stats["errors"] 
    }

def reset_cache_stats():
    """Reset the cache statistics"""
    for key in cache_stats:
        cache_stats[key] = 0

# Post-class instrumentation
for method_name in ['get', 'set', 'setex', 'delete', 'exists', 'expire', 'ttl',
                   'incr', 'decr', 'hget', 'hset', 'hmget', 'hmset', 'hgetall',
                   'lpush', 'rpush', 'lpop', 'rpop', 'lrange', 'ping']:
    method = getattr(TracedRedis, method_name)
    setattr(TracedRedis, method_name, TracedRedis._traced_operation(method_name)(method))
