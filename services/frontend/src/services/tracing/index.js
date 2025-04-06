// This is a temporary fixed version of the tracing index.js
import React from 'react';
import { trace, context, propagation } from '@opentelemetry/api';
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { Resource } from '@opentelemetry/resources';
import { SimpleSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load';
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

// Configuration settings
const OTEL_ENABLED = process.env.REACT_APP_OTEL_ENABLED === 'true';
const OTEL_ENDPOINT = process.env.REACT_APP_OTEL_ENDPOINT || '/api/v1/traces';
const SERVICE_NAME = process.env.REACT_APP_SERVICE_NAME || 'frontend-service';

let isInitialized = false;
let tracerProvider = null;

// Initialize OpenTelemetry tracing
export function initTracing() {
  if (isInitialized || !OTEL_ENABLED) {
    return;
  }

  try {
    console.log(`Initializing OpenTelemetry tracing for ${SERVICE_NAME}`);

    // Create a resource that identifies your application
    const resource = Resource.default().merge(
      new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]: SERVICE_NAME,
        [SemanticResourceAttributes.SERVICE_VERSION]: process.env.REACT_APP_VERSION || '1.0.0',
        'application.environment': process.env.NODE_ENV || 'development',
      })
    );

    // Create a tracer provider
    tracerProvider = new WebTracerProvider({
      resource,
    });

    // Configure span processor and exporter
    const otlpExporter = new OTLPTraceExporter({
      url: OTEL_ENDPOINT, // This will be proxied through Nginx
      headers: {},
    });

    // Add span processor to the provider
    tracerProvider.addSpanProcessor(new SimpleSpanProcessor(otlpExporter));

    // Register your tracer provider
    tracerProvider.register({
      contextManager: new ZoneContextManager(),
    });

    // Register instrumentations
    registerInstrumentations({
      instrumentations: [
        // Automatically trace page loads
        new DocumentLoadInstrumentation(),
        
        // Trace all fetch requests
        new FetchInstrumentation({
          propagateTraceHeaderCorsUrls: [
            // Allow trace header propagation for API requests
            /http:\/\/localhost:.*/,
            new RegExp(`${window.location.origin}.*`),
          ],
          // Add trace context to outgoing requests
          clearTimingResources: true,
        }),
        
        // Trace all XMLHttpRequests
        new XMLHttpRequestInstrumentation({
          propagateTraceHeaderCorsUrls: [
            /http:\/\/localhost:.*/,
            new RegExp(`${window.location.origin}.*`),
          ],
        }),
        
        // Trace user interactions (clicks, etc.)
        new UserInteractionInstrumentation(),
      ],
    });

    console.log('OpenTelemetry tracing initialized successfully');
    isInitialized = true;
  } catch (error) {
    console.error('Failed to initialize OpenTelemetry tracing:', error);
  }
}

// Create a tracer for manual instrumentation
export function getTracer(name = 'frontend') {
  if (!OTEL_ENABLED) {
    // Return a dummy tracer if tracing is disabled
    return {
      startActiveSpan: (spanName, options, fn) => {
        return fn({
          setAttribute: () => {},
          setStatus: () => {},
          end: () => {},
        });
      },
      startSpan: () => ({
        setAttribute: () => {},
        setStatus: () => {},
        end: () => {},
      }),
    };
  }

  return trace.getTracer(name);
}

// Extract trace context from carrier (usually headers)
export function extractTraceContext(carrier = {}) {
  // Normalize header keys to lowercase
  const normalizedCarrier = {};
  Object.keys(carrier).forEach(key => {
    normalizedCarrier[key.toLowerCase()] = carrier[key];
  });
  
  // Extract context using OpenTelemetry propagator
  return propagation.extract(context.active(), normalizedCarrier);
}

// Inject current trace context into carrier (usually headers)
export function injectTraceContext(carrier = {}) {
  // Make sure the carrier is an object with case-insensitive headers
  const normalizedCarrier = carrier || {};
  
  // Inject the current context into the carrier
  propagation.inject(context.active(), normalizedCarrier);
  
  return normalizedCarrier;
}

// Initialize tracing
initTracing();

export default {
  initTracing,
  getTracer,
  extractTraceContext,
  injectTraceContext,
};

// DO NOT ADD ANYTHING BELOW THIS COMMENT - PREVIOUS CODE HAD AN ERROR HERE
// export const contextPropagation = contextUtils;
