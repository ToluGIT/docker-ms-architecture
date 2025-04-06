from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, make_asgi_app
from fastapi.responses import JSONResponse
from fastapi import status
from slowapi import _rate_limit_exceeded_handler  
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .config import limiter
from app.middleware.trace_context import setup_trace_context_middleware
from app.middleware.tracing_middleware import setup_tracing_metrics_middleware
import redis
import requests
import time
import datetime 
import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, database
from .routers import items, users, auth
from app.security.credentials import CredentialManager
from . import tracing
from contextlib import nullcontext
import opentelemetry.trace as trace
from .utils.tracing_utils import traced
from .trace_metrics import track_operation_time, track_cache_operation, track_db_operation
from .trace_metrics import track_request_for_slo, update_slo_compliance
import logging

# Setup metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])

# Initialize FastAPI app
app = FastAPI(
    title="Nexa API",
    description="Diving into microservices platform for containerized applications",
    version="1.0.0",
    docs_url="/api-docs"
)

# Initialize tracer
tracer = tracing.setup_tracing(app=app, engine=database.engine)
if tracer:
    logger = logging.getLogger("api.main")
    logger.info("Tracing initialized successfully")

# Setup tracing middleware
setup_trace_context_middleware(app)

# Initialize tracing metrics middleware
setup_tracing_metrics_middleware(app)

# Initialize SLO metrics
from .trace_metrics import init_slo_info
init_slo_info()
logger.info("SLO metrics initialized")


# Register rate limit handler - add after app initialization
app.state.limiter = limiter
#app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  
# With this custom handler:
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please try again later.",
            "retry_after": 60  # Seconds until limit resets
        },
        headers={"Retry-After": "60"}
    )

# Add request tracking middleware first
@app.middleware("http")
async def track_requests(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    response = await call_next(request)
    status = response.status_code
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    return response

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Add origin validation middleware after request tracking but before CORS
@app.middleware("http")
async def validate_origin_middleware(request: Request, call_next):
    origin = request.headers.get("Origin")
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost").split(",")  #Take note of this (modify if frontend is listening on different port that default port 3000 for dev and 80 for production)
    
    # If there's an origin header and it's not in our allowed list
    if origin and origin not in allowed_origins:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Origin not allowed"}
        )
    
    # If no origin header or it's allowed, continue processing
    return await call_next(request)

# CORS configuration
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Explicit list of allowed methods
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],  # Explicit list of allowed headers
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],  # Expose rate limit headers
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Setup database
models.Base.metadata.create_all(bind=database.engine)

# Setup Redis connection with retry
def get_redis_client():
    redis_url = CredentialManager.get_redis_url()
    max_retries = 5
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Connect using the secure URL
            redis_client = redis.Redis.from_url(
                redis_url,
                socket_connect_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True,
                max_connections=100
            )
            redis_client.ping()  # Test the connection
            return redis_client
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            if attempt < max_retries - 1:
                print(f"Redis connection attempt {attempt+1} failed. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Failed to connect to Redis after {max_retries} attempts: {e}")
                # Return a dummy client that will log errors but not crash the app
                return DummyRedisClient()

class DummyRedisClient:
    """Fallback Redis client for failed connections"""
    def get(self, key):
        print(f"[WARNING] Dummy Redis GET: {key}")
        return None
     
    def setex(self, key, time, value):
        print(f"[WARNING] Dummy Redis SETEX: {key}")
        return True
    
    def ping(self):
        print("[WARNING] Dummy Redis PING")
        raise redis.exceptions.ConnectionError("Using dummy Redis client")
    
    def __init__(self):
        print("[WARNING] Using DummyRedisClient - rate limiting disabled")

# Initialize Redis client
redis_client = get_redis_client()

# Include routers
app.include_router(items.router)
app.include_router(users.router)
app.include_router(auth.router)

# Endpoints
@app.get("/")
@limiter.limit("20/minute")
def read_root(request: Request):
    return {"message": "Welcome to Nexa API"}

@app.get("/health")
@limiter.limit("30/minute") 
@track_operation_time("health_check", "api")
def health_check(request: Request):
    """System health check endpoint"""
    start_time = time.time()
    
    try:
        # Database check
        db = database.SessionLocal()
        with track_db_operation("query", "system"):
            db.execute(text("SELECT 1"))
            db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    finally:
        db.close()

    # Redis check
    try:
        # Existing code
        with track_cache_operation("ping", False):
            redis_client.ping()
        # New verification
        if not redis_client.ping():
            raise Exception("Redis responded but connection verification failed")
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    # Calculate total duration for SLO tracking
    duration = time.time() - start_time

    # Track for SLO
    endpoint_path = request.url.path    
    is_error = db_status != "healthy" or redis_status != "healthy"
    track_request_for_slo(
        endpoint="health_check",
        slo_name="api_health",
        latency=duration,
        is_error=is_error
    )
    
    # Update SLO compliance based on recent metrics
    update_slo_compliance(
        endpoint="health_check",
        slo_name="api_health",
        compliance_ratio=0.0 if is_error else 1.0,
        window="immediate"
    )

    return {
        "status": "operational" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        "version": "1.0.0",
        "components": {
            "database": {"status": db_status},
            "cache": {"status": redis_status}
        },
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/external-data")
@limiter.limit("10/minute")
@traced("get_external_data_endpoint", {"endpoint_type": "external"})
@track_operation_time("get_external_data", "api")
def get_external_data(request: Request):
    """Fetch external data with Redis caching"""
    start_time = time.time()
    cache_key = "external_data"
    is_error = False
    
    tracer = tracing.get_tracer()
    
    # Try cache first - with new cache tracking
    with tracer.start_as_current_span("redis_cache_lookup") if tracer else nullcontext():
        with track_cache_operation("get", False) as cache_op:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                # Update the cache hit status
                with track_cache_operation("hit", True):
                    # Calculate duration for SLO
                    duration = time.time() - start_time
                    # Track this request for SLO
                    track_request_for_slo(
                        endpoint="get_external_data",
                        slo_name="external_data",
                        latency=duration,
                        is_error=False
                    )
                    return {"source": "cache", "data": cached_data.decode('utf-8')}
    
    # Fetch from API if not in cache
    try:
        with tracer.start_as_current_span("github_api_request") if tracer else nullcontext():
            with track_operation_time("github_api_request", "external_api"):
                response = requests.get("https://api.github.com/repos/docker/docker")
                data = response.json()
            
        with tracer.start_as_current_span("redis_cache_store") if tracer else nullcontext():
            with track_cache_operation("set", False):
                redis_client.setex(cache_key, 300, str(data))
        
        # Calculate duration for SLO
        duration = time.time() - start_time
        # Track this request for SLO
        track_request_for_slo(
            endpoint="get_external_data",
            slo_name="external_data",
            latency=duration,
            is_error=False
        )
            
        return {"source": "api", "data": data}
    except requests.RequestException as e:
        is_error = True
        if tracer:
            current_span = trace.get_current_span()
            current_span.set_status(trace.Status(trace.StatusCode.ERROR))
            current_span.record_exception(e)
        
        # Track error for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="get_external_data",
            slo_name="external_data",
            latency=duration,
            is_error=True
        )
            
        raise HTTPException(status_code=500, detail=f"External API error: {str(e)}")
# Add these imports after existing Redis import
try:
    from .cache_tracing import instrument_redis
    from .repositories.cached_user_repository import CachedUserRepository
    traced_redis_available = True
except ImportError:
    traced_redis_available = False

# Replace Redis client initialization with traced version
# Find and modify the Redis initialization section:
# Setup Redis connection with retry
def get_redis_client():
    """Get a Redis client with tracing if available"""
    redis_url = CredentialManager.get_redis_url()
    max_retries = 5
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Create the standard Redis client first
            base_client = redis.Redis.from_url(
                redis_url,
                socket_connect_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True,
                max_connections=100
            )
            
            # Test the connection
            base_client.ping()
            
            # Wrap with tracing if available
            if traced_redis_available:
                logger.info("Instrumenting Redis client with tracing")
                return instrument_redis(base_client)
            else:
                return base_client
                
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            if attempt < max_retries - 1:
                print(f"Redis connection attempt {attempt+1} failed. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Failed to connect to Redis after {max_retries} attempts: {e}")
                # Return a dummy client that will log errors but not crash the app
                return DummyRedisClient()

# Modify the external data function to use traced spans
@app.get("/external-data")
@limiter.limit("10/minute")
def get_external_data(request: Request):
    """Fetch external data with Redis caching"""
    cache_key = "external_data"
    
    # Get tracer if available
    current_tracer = tracing.get_tracer() if 'tracing' in globals() else None
    
    # Create a context manager for the span based on availability
    cache_lookup_ctx = current_tracer.start_as_current_span("redis_cache_lookup") if current_tracer else nullcontext()
    
    # Try cache first
    with cache_lookup_ctx:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return {"source": "cache", "data": cached_data.decode('utf-8')}
    
    # Fetch from API if not in cache
    try:
        api_request_ctx = current_tracer.start_as_current_span("github_api_request") if current_tracer else nullcontext()
        with api_request_ctx:
            response = requests.get("https://api.github.com/repos/docker/docker")
            data = response.json()
        
        cache_store_ctx = current_tracer.start_as_current_span("redis_cache_store") if current_tracer else nullcontext()
        with cache_store_ctx:
            redis_client.setex(cache_key, 300, str(data))
            
        return {"source": "api", "data": data}
    except requests.RequestException as e:
        if current_tracer:
            current_span = trace.get_current_span()
            current_span.set_status(trace.Status(trace.StatusCode.ERROR))
            current_span.record_exception(e)
            
        raise HTTPException(status_code=500, detail=f"External API error: {str(e)}")


# Add a new health endpoint that includes Redis stats
@app.get("/redis-stats")
def redis_stats():
    """Get Redis cache statistics"""
    try:
        if traced_redis_available:
            from .cache_tracing.redis_tracing import get_cache_stats
            stats = get_cache_stats()
            return {
                "status": "enabled",
                "stats": stats
            }
        else:
            return {
                "status": "tracing_not_available",
                "stats": {}
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
