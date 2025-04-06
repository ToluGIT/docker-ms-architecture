"""
Enhanced trace metrics module for Prometheus integration with OpenTelemetry
with comprehensive SLO support
"""
import time
import logging
import functools
from prometheus_client import Histogram, Counter, Gauge, Info
from opentelemetry import trace
from typing import Dict, Any, Optional, List

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Define Prometheus metrics
REQUEST_LATENCY = Histogram(
    'request_duration_seconds', 
    'Request latency in seconds',
    ['method', 'endpoint', 'trace_sampled']
)

SPAN_DURATION = Histogram(
    'span_duration_seconds',
    'Span duration in seconds',
    ['service', 'operation', 'status']
)

ERROR_COUNTER = Counter(
    'trace_errors_total',
    'Total number of errors in traces',
    ['service', 'operation', 'error_type']
)

OPERATION_COUNTER = Counter(
    'trace_operations_total',
    'Total number of operations executed',
    ['service', 'operation']
)

DB_OPERATION_LATENCY = Histogram(
    'db_operation_duration_seconds',
    'Database operation latency in seconds',
    ['operation_type', 'table', 'trace_id']
)

CACHE_OPERATION_LATENCY = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation latency in seconds',
    ['operation', 'hit', 'trace_id']
)

# SLO metrics
SLO_LATENCY_BUCKET = Histogram(
    'slo_request_latency_seconds',
    'Request latency for SLO tracking',
    ['endpoint', 'slo']
)

SLO_ERROR_COUNTER = Counter(
    'slo_errors_total',
    'Total number of errors for SLO tracking',
    ['endpoint', 'slo'] 
)

SLO_COMPLIANCE = Gauge(
    'slo_compliance_ratio',
    'Compliance with SLO targets',
    ['endpoint', 'slo', 'window']
)

# New: SLO budget tracking
SLO_ERROR_BUDGET = Gauge(
    'slo_error_budget_remaining',
    'Remaining error budget for the SLO',
    ['slo', 'window']
)

# New: SLO information
SLO_INFO = Info(
    'slo_info',
    'Information about defined SLOs'
)

# SLO definitions
SLO_DEFINITIONS = {
    'api_health': {
        'description': 'API Health endpoint latency',
        'target': 0.95,  # 95% of requests under target latency
        'latency_target': 0.1,  # 100ms
        'error_budget': 0.05,  # 5% error budget
        'windows': ['5m', '1h', '24h'],  # Evaluation windows
        'endpoints': ['health_check', 'read_root', '/health']
    },
    'external_data': {
        'description': 'External data retrieval latency',
        'target': 0.90,  # 90% of requests under target latency
        'latency_target': 0.3,  # 300ms
        'error_budget': 0.10,  # 10% error budget
        'windows': ['5m', '1h', '24h'],
        'endpoints': ['get_external_data']
    },
    'data_access': {
        'description': 'Database access operations latency',
        'target': 0.95,  # 95% of requests under target latency
        'latency_target': 0.2,  # 200ms
        'error_budget': 0.05,  # 5% error budget
        'windows': ['5m', '1h', '24h'],
        'endpoints': ['read_users', 'read_items', 'create_user', 'create_item']
    }
}

# Initialize SLO info
def init_slo_info():
    """Initialize SLO info metric with definitions"""
    # Prepare SLO information
    for slo_name, slo_def in SLO_DEFINITIONS.items():
        SLO_INFO.info({
            'name': slo_name,
            'description': slo_def['description'],
            'target': str(slo_def['target']),
            'latency_target_ms': str(slo_def['latency_target'] * 1000),
            'error_budget': str(slo_def['error_budget']),
            'windows': ','.join(slo_def['windows']),
            'endpoints': ','.join(slo_def['endpoints'])
        })
    
    logger.info("SLO definitions initialized for Prometheus")

# Track time taken for an operation and record in Prometheus
def track_operation_time(operation_name: str, service: str = "api"):
    """Decorator to track operation time in Prometheus metrics"""
    def decorator(func):
        @functools.wraps(func) 
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Get current span context for correlation
            current_span = trace.get_current_span()
            span_context = current_span.get_span_context() if current_span else None
            trace_id = format(span_context.trace_id, '032x') if span_context else "unknown"
            
            # Track this operation
            OPERATION_COUNTER.labels(
                service=service,
                operation=operation_name
            ).inc()
            
            try:
                # Execute the original function
                result = func(*args, **kwargs)
                
                # Record successful execution time
                duration = time.time() - start_time
                SPAN_DURATION.labels(
                    service=service,
                    operation=operation_name,
                    status="success"
                ).observe(duration)
                
                return result
            except Exception as e:
                # Record error
                ERROR_COUNTER.labels(
                    service=service,
                    operation=operation_name,
                    error_type=e.__class__.__name__
                ).inc()
                
                # Record error execution time 
                duration = time.time() - start_time
                SPAN_DURATION.labels(
                    service=service,
                    operation=operation_name,
                    status="error"
                ).observe(duration)
                
                # Re-raise the exception
                raise
        return wrapper
    return decorator

# Track database operations with trace ID for exemplars
def track_db_operation(operation_type: str, table: str):
    """Record database operation metrics with trace correlation"""
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context() if current_span else None
    trace_id = format(span_context.trace_id, '032x') if span_context else "unknown"
    
    start_time = time.time()
    
    # Return context manager for timing
    class TimerContextManager:
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - start_time
            DB_OPERATION_LATENCY.labels(
                operation_type=operation_type,
                table=table,
                trace_id=trace_id
            ).observe(duration)
            
            if exc_type:
                # Record error
                ERROR_COUNTER.labels(
                    service="db",
                    operation=f"{operation_type}_{table}",
                    error_type=exc_type.__name__
                ).inc()
    
    return TimerContextManager()

# Track cache operations with hit/miss info
def track_cache_operation(operation: str, hit: bool):
    """Record cache operation metrics with trace correlation"""
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context() if current_span else None
    trace_id = format(span_context.trace_id, '032x') if span_context else "unknown"
    
    start_time = time.time()
    
    # Return context manager for timing
    class TimerContextManager:
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - start_time
            CACHE_OPERATION_LATENCY.labels(
                operation=operation,
                hit="true" if hit else "false",
                trace_id=trace_id
            ).observe(duration)
            
            if exc_type:
                # Record error
                ERROR_COUNTER.labels(
                    service="cache",
                    operation=operation,
                    error_type=exc_type.__name__
                ).inc()
    
    return TimerContextManager()

# Track API request for SLO monitoring
def track_request_for_slo(endpoint: str, slo_name: str, latency: float, is_error: bool = False):
    """Record request metrics for SLO tracking"""
    # Check if endpoint is valid for this SLO
    slo_def = SLO_DEFINITIONS.get(slo_name)
    if not slo_def:
        logger.debug(f"SLO {slo_name} not found in definitions")
        return
        
    if endpoint not in slo_def.get('endpoints', []):
        logger.debug(f"Endpoint {endpoint} not in SLO {slo_name} endpoints: {slo_def.get('endpoints', [])}")
        return
    
    logger.debug(f"Recording SLO {slo_name} for endpoint {endpoint}: latency={latency}, error={is_error}")

    if not slo_def or endpoint not in slo_def.get('endpoints', []):
        logger.warning(f"Endpoint {endpoint} not configured for SLO {slo_name}")
        return
    
    # Get current span for correlation
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context() if current_span else None
    trace_id = format(span_context.trace_id, '032x') if span_context else "unknown"
    
    # Record latency for SLO tracking with trace exemplar
    SLO_LATENCY_BUCKET.labels(
        endpoint=endpoint,
        slo=slo_name
    ).observe(latency)
    
    # Count errors if any
    if is_error:
        SLO_ERROR_COUNTER.labels(
            endpoint=endpoint,
            slo=slo_name
        ).inc()
    
    # Log SLO performance at debug level
    target_ms = slo_def['latency_target'] * 1000
    latency_ms = latency * 1000
    is_within_slo = latency <= slo_def['latency_target']
    
    logger.debug(
        f"SLO {slo_name}: {endpoint} - {latency_ms:.2f}ms / {target_ms:.0f}ms target - "
        f"{'✓' if is_within_slo else '✗'} - {trace_id}"
    )

# Update SLO compliance ratio based on recent data
def update_slo_compliance(endpoint: str, slo_name: str, compliance_ratio: float, window: str = "5m"):
    """Update the SLO compliance gauge"""
    # Validate inputs
    if window not in ["immediate", "5m", "1h", "24h"]:
        logger.warning(f"Invalid window for SLO compliance: {window}")
        return
    
    # Validate SLO exists
    if slo_name not in SLO_DEFINITIONS:
        logger.warning(f"Unknown SLO: {slo_name}")
        return
    
    # Set the SLO compliance gauge
    SLO_COMPLIANCE.labels(
        endpoint=endpoint,
        slo=slo_name,
        window=window
    ).set(compliance_ratio)
    
    # Update error budget if this is a window-based compliance update
    if window != "immediate":
        slo_def = SLO_DEFINITIONS[slo_name]
        target = slo_def["target"]
        error_budget = slo_def["error_budget"]
        
        # Calculate remaining error budget
        # If compliance is 0.94 and target is 0.95, we've used (0.95-0.94)/0.05 = 20% of our budget
        if compliance_ratio < target:
            budget_used_ratio = (target - compliance_ratio) / error_budget
            budget_remaining = max(0, 1 - budget_used_ratio)
        else:
            budget_remaining = 1.0
            
        # Update the error budget gauge
        SLO_ERROR_BUDGET.labels(
            slo=slo_name,
            window=window
        ).set(budget_remaining)
        
        # Log when budget is getting low
        if budget_remaining < 0.2:
            logger.warning(
                f"SLO {slo_name} error budget critically low: {budget_remaining:.1%} remaining "
                f"for {window} window"
            )
        elif budget_remaining < 0.5:
            logger.info(
                f"SLO {slo_name} error budget below 50%: {budget_remaining:.1%} remaining "
                f"for {window} window"
            )


# Initialize SLOs on module import
init_slo_info()
