"""
Enhanced SQLAlchemy tracing for OpenTelemetry
"""
import functools
import time
import logging
from typing import Optional, Callable, Dict, Any
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import Session

# Try to import OpenTelemetry, handle gracefully if not available
try:
    from opentelemetry import trace
    from opentelemetry.trace.status import Status, StatusCode
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Track connection pool stats
pool_stats = {
    "checked_out": 0,
    "checked_in": 0,
    "created": 0,
    "disposed": 0
}

def instrument_database(engine: Engine) -> None:
    """
    Add instrumentation to the SQLAlchemy engine for pool tracking
    
    Args:
        engine: The SQLAlchemy engine to instrument
    """
    if not engine:
        logger.warning("No SQLAlchemy engine provided for instrumentation")
        return
    
    # Track connection pool activity
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        pool_stats["checked_out"] += 1
    
    @event.listens_for(engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        pool_stats["checked_in"] += 1
    
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        pool_stats["created"] += 1
    
    @event.listens_for(engine, "close")
    def receive_close(dbapi_connection, connection_record):
        pool_stats["disposed"] += 1
    
    logger.info("Database pool tracking instrumentation added")

def enable_statement_tracing(engine: Engine) -> None:
    """
    Add SQL statement tracing to capture query details
    
    Args:
        engine: The SQLAlchemy engine to instrument
    """
    if not TRACING_AVAILABLE:
        logger.warning("OpenTelemetry not available, SQL statement tracing disabled")
        return
    
    if not engine:
        logger.warning("No SQLAlchemy engine provided for SQL tracing")
        return
    
    # Before query execution
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Store execution start time in context
        context._query_start_time = time.time()
        
        # Get current tracer and span
        tracer = trace.get_tracer(__name__)
        
        # Create a span for this database query
        span = tracer.start_span(
            name="sql_query",
            attributes={
                "db.system": "postgresql",
                "db.statement": statement,
                "db.statement_type": statement.split()[0].upper() if statement else "",
                "db.user": conn.engine.url.username,
                "db.name": conn.engine.url.database,
                "db.connection_id": id(conn),
                "db.execution_type": "executemany" if executemany else "execute"
            }
        )
        
        # Store the span in context for later retrieval
        context._span = span
    
    # After query execution
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Calculate query execution time
        if hasattr(context, "_query_start_time"):
            execution_time = time.time() - context._query_start_time
            
            # If we have a span from the before_cursor_execute event
            if hasattr(context, "_span"):
                span = context._span
                
                # Add execution time and row count attributes
                span.set_attribute("db.execution_time_ms", execution_time * 1000)
                
                try:
                    if hasattr(cursor, "rowcount"):
                        span.set_attribute("db.result_rows", cursor.rowcount)
                except Exception:
                    pass
                
                # End the span
                span.end()
    
    logger.info("SQL statement tracing enabled")

@contextmanager
def traced_session(session: Session, operation_name: str = "database_operation") -> Session:
    """
    Context manager to trace database session operations
    
    Args:
        session: SQLAlchemy session to trace
        operation_name: Name for the database operation span
    
    Example:
        with traced_session(db, "get_user_data") as session:
            user = session.query(User).filter(User.id == user_id).first()
    """
    if not TRACING_AVAILABLE:
        # If tracing is not available, just yield the session
        yield session
        return
    
    # Get current tracer
    tracer = trace.get_tracer(__name__)
    
    # Start span for the database operation
    with tracer.start_as_current_span(
        operation_name,
        attributes={
            "db.type": "postgresql",
            "db.operation": operation_name,
            "db.session_id": id(session)
        }
    ) as span:
        start_time = time.time()
        
        try:
            # Yield the session for use in the with block
            yield session
            
            # Set span status to success
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            # Record the exception in the span
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            span.set_attribute("error.message", str(e))
            span.set_attribute("error.type", e.__class__.__name__)
            
            # Re-raise the exception
            raise
        
        finally:
            # Record the execution time
            execution_time = time.time() - start_time
            span.set_attribute("db.execution_time_ms", execution_time * 1000)


# Create a decorator for database operations
def traced_db_operation(operation_name: Optional[str] = None, 
                     attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace database operations
    
    Args:
        operation_name: Name for the database operation span
        attributes: Additional attributes to add to the span
    
    Example:
        @traced_db_operation("get_user_by_id")
        def get_user(db: Session, user_id: int):
            return db.query(User).filter(User.id == user_id).first()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # If not tracing or no session in args/kwargs, just call the function
            if not TRACING_AVAILABLE:
                return func(*args, **kwargs)
            
            # Find the session object in args or kwargs
            session = None
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                    break
            
            if session is None:
                for key, value in kwargs.items():
                    if isinstance(value, Session):
                        session = value
                        break
            
            # If we couldn't find a session, just call the function
            if session is None:
                return func(*args, **kwargs)
            
            # Get the operation name
            name = operation_name or f"db_{func.__name__}"
            
            # Get the tracer
            tracer = trace.get_tracer(__name__)
            
            # Prepare span attributes
            span_attributes = {
                "db.type": "postgresql",
                "db.operation": name,
                "db.session_id": id(session),
                "code.function": func.__name__,
                "code.namespace": func.__module__
            }
            
            # Add custom attributes if provided
            if attributes:
                span_attributes.update(attributes)
            
            # Start span for the database operation
            with tracer.start_as_current_span(
                name,
                attributes=span_attributes
            ) as span:
                start_time = time.time()
                
                try:
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # Set span status to success
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    # Record the exception in the span
                    span.set_status(Status(StatusCode.ERROR))
                    span.record_exception(e)
                    span.set_attribute("error.message", str(e))
                    span.set_attribute("error.type", e.__class__.__name__)
                    
                    # Re-raise the exception
                    raise
                
                finally:
                    # Record the execution time
                    execution_time = time.time() - start_time
                    span.set_attribute("db.execution_time_ms", execution_time * 1000)
        
        return wrapper
    
    return decorator

def get_pool_stats():
    """Get the current connection pool statistics"""
    return pool_stats
