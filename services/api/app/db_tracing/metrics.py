"""
Database metrics integration for tracing and monitoring
"""
import time
import logging
from sqlalchemy import event
from sqlalchemy.engine.base import Engine
from ..trace_metrics import DB_OPERATION_LATENCY, ERROR_COUNTER, track_db_operation
from opentelemetry import trace

logger = logging.getLogger(__name__)

def enable_db_metrics(engine: Engine) -> None:
    """
    Add metrics collection to the SQLAlchemy engine
    
    Args:
        engine: The SQLAlchemy engine to instrument
    """
    if not engine:
        logger.warning("No SQLAlchemy engine provided for metrics")
        return
    
    # Before query execution
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Store execution start time in context
        context._query_start_time = time.time()
        
        # Determine operation type from statement
        operation_type = statement.split()[0].upper() if statement else "UNKNOWN"
        
        # Try to extract table name from statement
        # This is a simplified approach, proper SQL parsing would be better
        table_name = "unknown"
        if " FROM " in statement:
            # For SELECT statements
            table_parts = statement.split(" FROM ")[1].split()
            if table_parts:
                table_name = table_parts[0].strip().rstrip(';')
        elif "INSERT INTO" in statement:
            # For INSERT statements
            table_parts = statement.split("INSERT INTO ")[1].split()
            if table_parts:
                table_name = table_parts[0].strip().rstrip(';')
        elif "UPDATE" in statement:
            # For UPDATE statements
            table_parts = statement.split("UPDATE ")[1].split()
            if table_parts:
                table_name = table_parts[0].strip().rstrip(';')
        elif "DELETE FROM" in statement:
            # For DELETE statements
            table_parts = statement.split("DELETE FROM ")[1].split()
            if table_parts:
                table_name = table_parts[0].strip().rstrip(';')
        
        # Store operation details in context
        context._db_operation = {
            "type": operation_type,
            "table": table_name
        }
    
    # After query execution
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Calculate query execution time
        if hasattr(context, "_query_start_time"):
            execution_time = time.time() - context._query_start_time
            
            # Get operation details
            if hasattr(context, "_db_operation"):
                operation_type = context._db_operation.get("type", "UNKNOWN")
                table = context._db_operation.get("table", "unknown")
                
                # Get trace info
                current_span = trace.get_current_span()
                span_context = current_span.get_span_context() if current_span else None
                trace_id = format(span_context.trace_id, '032x') if span_context else "unknown"
                
                # Record metrics
                DB_OPERATION_LATENCY.labels(
                    operation_type=operation_type,
                    table=table,
                    trace_id=trace_id
                ).observe(execution_time)
    
    # Handle database errors
    @event.listens_for(engine, "handle_error")
    def handle_error(context):
        # Extract error info
        error = context.original_exception
        error_type = error.__class__.__name__
        
        # Get operation details if available
        if hasattr(context, "_db_operation"):
            operation_type = context._db_operation.get("type", "UNKNOWN")
            table = context._db_operation.get("table", "unknown")
        else:
            operation_type = "ERROR"
            table = "unknown"
        
        # Record the error
        ERROR_COUNTER.labels(
            service="db",
            operation=f"{operation_type}_{table}",
            error_type=error_type
        ).inc()
        
        # Log the error
        logger.error(f"Database error: {error_type} in {operation_type} on {table}")
    
    logger.info("Database metrics collection enabled")

# Helper function to use in repository methods
def with_metrics(operation_type: str, table: str):
    """Decorator for repository methods to add metrics tracking"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with track_db_operation(operation_type, table):
                return func(*args, **kwargs)
        return wrapper
    return decorator
