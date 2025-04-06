"""
Tracing configuration module for the API service.
Sets up OpenTelemetry tracing with Jaeger exporter.
"""
import os
import logging
from typing import Optional

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.propagators.b3 import B3Format
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from app.middleware.trace_context import setup_trace_context_middleware

# Create logger
logger = logging.getLogger("api.tracing")

# Global tracer instance
tracer = None

def setup_tracing(app=None, engine=None, service_name: str = "api-service"):
    """
    Configure OpenTelemetry tracing with Jaeger exporter.
    
    Args:
        app: FastAPI application instance for instrumentation
        engine: SQLAlchemy engine for database instrumentation
        service_name: Name to identify this service in traces
    """
    global tracer
    
    # Check if tracing should be enabled
    if os.getenv("ENABLE_TRACING", "true").lower() != "true":
        logger.info("Tracing is disabled by configuration")
        return None
    
    try:
        logger.info("Initializing OpenTelemetry tracing")
        
        set_global_textmap(CompositePropagator([
           TraceContextTextMapPropagator(),  # W3C Trace Context (standard)
           B3Format(),                       # B3 format (used by many systems)
           W3CBaggagePropagator()            # W3C Baggage (for additional context)
        ]))
        logger.info("Trace context propagators configured")
        
        # Configure the tracer provider
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        
        # Get the Jaeger endpoint from environment or use default
        otlp_endpoint = os.getenv("OTLP_ENDPOINT", "jaeger-tracing:4317")
        
        # Create OTLP exporter and add it to the provider
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)
        
        # Set the global tracer provider
        trace.set_tracer_provider(provider)
        
        # Get a tracer instance
        tracer = trace.get_tracer(__name__)
        
        # Instrument libraries if instances are provided
        if app:
            logger.info("Instrumenting FastAPI")
            FastAPIInstrumentor.instrument_app(app)
 
            setup_trace_context_middleware(app)
            logger.info("Trace context middleware added to FastAPI app")
        
        # Instrument requests library for HTTP calls
        logger.info("Instrumenting Requests library")
        RequestsInstrumentor().instrument()
        
        # Instrument SQLAlchemy if engine is provided
        if engine:
            logger.info("Instrumenting SQLAlchemy")
            SQLAlchemyInstrumentor().instrument(engine=engine)
        
        # Instrument Redis (this will capture all Redis clients)
        logger.info("Instrumenting Redis")
        RedisInstrumentor().instrument()
        
        logger.info("Tracing initialization complete")
        return tracer
    
    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return None

def get_tracer():
    """
    Get the configured tracer instance.
    
    Returns:
        Tracer instance or None if tracing is not initialized
    """
    global tracer
    return tracer
