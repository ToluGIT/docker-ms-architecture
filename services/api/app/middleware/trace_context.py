# services/api/app/middleware/trace_context.py
from fastapi import Request
from opentelemetry import trace
from opentelemetry import context  # Add this import
from opentelemetry.propagate import extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import logging

logger = logging.getLogger(__name__)

class TraceContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle trace context propagation and request correlation.
    
    This middleware:
    1. Extracts trace context from incoming requests
    2. Creates a correlation ID if not present
    3. Ensures all outgoing requests include trace context
    4. Adds correlation ID to the response headers
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID if not present
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Extract trace context from headers
        carrier = {}
        for key, value in request.headers.items():
            carrier[key.lower()] = value
        
        # Use W3C Trace Context standard for propagation
        ctx = extract(carrier)
        token = context.attach(ctx)
        
        # Record trace context details for debugging
        current_span = trace.get_current_span()
        if current_span.is_recording():
            current_span.set_attribute("correlation_id", correlation_id)
            
            # Log incoming trace details at debug level
            trace_id = trace.get_current_span().get_span_context().trace_id
            span_id = trace.get_current_span().get_span_context().span_id
            logger.debug(f"Request received: correlation_id={correlation_id}, trace_id={format(trace_id, '032x')}, span_id={format(span_id, '016x')}")
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Optional: Add trace ID for debugging
            if trace.get_current_span().get_span_context().trace_id:
                trace_id = trace.get_current_span().get_span_context().trace_id
                response.headers["X-Trace-ID"] = format(trace_id, '032x')
            
            return response
            
        except Exception as e:
            # Record exception in current span
            current_span = trace.get_current_span()
            if current_span.is_recording():
                current_span.record_exception(e)
                current_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise
        finally:
            # Detach the context
            context.detach(token)

# Helper function to configure the middleware
def setup_trace_context_middleware(app):
    """Configure and add the trace context middleware to the FastAPI app"""
    app.add_middleware(TraceContextMiddleware)
    logger.info("Trace context middleware configured")
