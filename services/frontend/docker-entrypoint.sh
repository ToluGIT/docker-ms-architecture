#!/bin/sh
set -e

# Check environment variables and set defaults
if [ "$REACT_APP_OTEL_ENABLED" = "true" ]; then
  echo "OpenTelemetry tracing is enabled"
else
  echo "OpenTelemetry tracing is disabled"
fi

# Set the OTEL endpoint based on environment
if [ -z "$REACT_APP_OTEL_ENDPOINT" ]; then
  if [ "$NODE_ENV" = "production" ]; then
    export REACT_APP_OTEL_ENDPOINT="/api/v1/traces"
  else
    export REACT_APP_OTEL_ENDPOINT="http://localhost:4318/v1/traces"
  fi
fi

echo "Using OTEL endpoint: $REACT_APP_OTEL_ENDPOINT"
echo "Service name: ${REACT_APP_SERVICE_NAME:-frontend-service}"

# Start the application
exec "$@"
