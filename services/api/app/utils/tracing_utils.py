"""
Tracing utilities for adding custom spans to functions.
"""
import functools
import time
from typing import Any, Callable, Dict, Optional

from opentelemetry import trace
from app.tracing import get_tracer


def traced(span_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to add a custom span around a function.
    
    Args:
        span_name: Name for the span (defaults to function name if not provided)
        attributes: Dictionary of attributes to add to the span
    
    Example:
        @traced("process_user_data", {"user_type": "premium"})
        def process_user(user_id: int):
            # This function will be traced with the given span name and attributes
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the tracer instance
            tracer = get_tracer()
            if not tracer:
                # If tracing is not initialized, just call the function
                return func(*args, **kwargs)
            
            # Determine span name
            name = span_name or f"{func.__module__}.{func.__name__}"
            
            # Create and add attributes
            span_attributes = attributes.copy() if attributes else {}
            
            # Start the span
            with tracer.start_as_current_span(name, attributes=span_attributes) as span:
                # Record start time
                start_time = time.time()
                
                try:
                    # Call the original function
                    result = func(*args, **kwargs)
                    
                    # Record success
                    span.set_attribute("status", "success")
                    
                    return result
                except Exception as e:
                    # Record error
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                    span.record_exception(e)
                    span.set_attribute("error.type", e.__class__.__name__)
                    span.set_attribute("error.message", str(e))
                    
                    # Re-raise the exception
                    raise
                finally:
                    # Record duration
                    duration = time.time() - start_time
                    span.set_attribute("duration_seconds", duration)
        
        return wrapper
    
    return decorator


def traced_function(func: Callable) -> Callable:
    """
    Simple decorator for tracing a function without additional parameters.
    Uses the function name as the span name.
    
    Example:
        @traced_function
        def process_data():
            # This function will be traced with span name "process_data"
    """
    return traced()(func)
