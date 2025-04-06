// services/frontend/src/services/tracing/context.js
// Complete file replacement

import { context, propagation, trace } from '@opentelemetry/api';

/**
 * Extract trace context from carrier (usually headers)
 * 
 * @param {Object} carrier - Usually HTTP headers
 * @returns {Object} Context object
 */
export function extractTraceContext(carrier = {}) {
  // Normalize header keys to lowercase
  const normalizedCarrier = {};
  Object.keys(carrier).forEach(key => {
    normalizedCarrier[key.toLowerCase()] = carrier[key];
  });
  
  // Extract context using OpenTelemetry propagator
  return propagation.extract(context.active(), normalizedCarrier);
}

/**
 * Inject current trace context into carrier (usually headers)
 * 
 * @param {Object} carrier - Usually HTTP headers object to inject context into
 * @returns {Object} The carrier with injected trace context
 */
export function injectTraceContext(carrier = {}) {
  // Make sure the carrier is an object with case-insensitive headers
  const normalizedCarrier = carrier || {};
  
  // Inject the current context into the carrier
  propagation.inject(context.active(), normalizedCarrier);
  
  // Log trace context at debug level
  const currentSpan = trace.getSpan(context.active());
  if (currentSpan) {
    const spanContext = currentSpan.spanContext();
    console.debug('Injected trace context:', {
      traceId: spanContext.traceId,
      spanId: spanContext.spanId
    });
  }
  
  return normalizedCarrier;
}

/**
 * Get the current trace ID for logging or display
 * 
 * @returns {string|null} Current trace ID or null if not available
 */
export function getCurrentTraceId() {
  const currentSpan = trace.getSpan(context.active());
  if (currentSpan) {
    return currentSpan.spanContext().traceId;
  }
  return null;
}

/**
 * Get the current span ID for logging or display
 * 
 * @returns {string|null} Current span ID or null if not available
 */
export function getCurrentSpanId() {
  const currentSpan = trace.getSpan(context.active());
  if (currentSpan) {
    return currentSpan.spanContext().spanId;
  }
  return null;
}

/**
 * Execute callback within the context of a given parent context
 * 
 * @param {Object} parentContext - Context object from extractTraceContext
 * @param {Function} callback - Function to execute within the context
 * @returns {*} The result of the callback
 */
export function withContext(parentContext, callback) {
  return context.with(parentContext, callback);
}
