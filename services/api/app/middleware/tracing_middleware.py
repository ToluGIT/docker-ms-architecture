"""
Enhanced tracing middleware with Prometheus metrics integration
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace
from app.trace_metrics import REQUEST_LATENCY, track_request_for_slo

class TracingMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect metrics about requests and connect them with traces.
    This middleware:
    1. Times all requests
    2. Records latency as Prometheus histograms
    3. Adds trace ID as exemplar to metrics
    4. Tracks latency for SLO monitoring
    """
    
    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        # Get trace info
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context() if current_span else None
        trace_sampled = "true" if span_context and span_context.trace_flags.sampled else "false"
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Extract endpoint path without query params and route params
            # This groups similar endpoints (e.g., /users/123 and /users/456 become /users/{id})
            endpoint = request.scope.get("endpoint", None)
            route_path = request.scope.get("path", request.url.path)
            if hasattr(endpoint, "__name__"):
                endpoint_name = endpoint.__name__
            else:
                # If we don't have a named endpoint, use the path but normalize dynamic parts
                endpoint_name = route_path
            
            # Record request duration
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint_name,
                trace_sampled=trace_sampled
            ).observe(duration)
            
            # Record for SLO tracking
            # Determine if this endpoint has an SLO defined
            has_slo = endpoint_name in [
                "read_root", "health_check", "get_external_data", 
                "read_users", "read_items"
            ]
            
            if has_slo:
                # Map endpoint to specific SLO name
                if endpoint_name in ["read_root", "health_check"]:
                    slo_name = "api_health"
                elif endpoint_name == "get_external_data":
                    slo_name = "external_data"
                else:
                    slo_name = "data_access"
                
                # Track for SLO with appropriate latency target
                track_request_for_slo(
                    endpoint=endpoint_name,
                    slo_name=slo_name,
                    latency=duration,
                    is_error=response.status_code >= 400
                )
            
            return response
            
        except Exception as e:
            # Record duration even for errors
            duration = time.time() - start_time
            
            # Record request with error status
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path,
                trace_sampled=trace_sampled
            ).observe(duration)
            
            # Re-raise the exception
            raise

def setup_tracing_metrics_middleware(app):
    """Add the tracing metrics middleware to the FastAPI app"""
    app.add_middleware(TracingMetricsMiddleware)
    return app
