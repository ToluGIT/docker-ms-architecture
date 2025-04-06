#!/bin/bash

echo "Verifying API Tracing Integration"
echo "--------------------------------"

# Check if Jaeger is running
JAEGER_CONTAINER=$(docker ps --filter "name=jaeger" --format "{{.Names}}")
if [ -z "$JAEGER_CONTAINER" ]; then
    echo "❌ Jaeger container is not running. Start it first with:"
    echo "  ./microservices start-tracing"
    exit 1
fi

echo "✅ Jaeger container is running"

# Check if API is running
API_CONTAINER=$(docker ps --filter "name=api" --format "{{.Names}}")
if [ -z "$API_CONTAINER" ]; then
    echo "❌ API container is not running. Start it first with:"
    echo "  ./microservices start --services api"
    exit 1
fi

echo "✅ API container is running"

# Generate some traffic to create traces
echo "Generating API traffic to create traces..."
curl -s http://localhost:8000/ > /dev/null
curl -s http://localhost:8000/health > /dev/null
curl -s http://localhost:8000/external-data > /dev/null
curl -s http://localhost:8000/users > /dev/null

echo "✅ Traffic sent to API endpoints"

# Wait a moment for traces to be processed
echo "Waiting for traces to be processed..."
sleep 3

# Check if traces are available in Jaeger
echo "Checking for traces in Jaeger..."
SERVICES=$(curl -s "http://localhost:16686/api/services" | grep -o '"api-service"')

if [ ! -z "$SERVICES" ]; then
    echo "✅ API service traces found in Jaeger!"
    echo "View traces at: http://localhost:16686/search?service=api-service"
else
    echo "❌ No API service traces found in Jaeger. Possible issues:"
    echo "  - OpenTelemetry configuration might be incorrect"
    echo "  - API might not be connecting to Jaeger properly"
    echo "  - There might be a network issue between API and Jaeger"
    
    # Check network connectivity
    echo "Testing network connectivity from API to Jaeger..."
    docker exec $API_CONTAINER ping -c 1 jaeger-tracing
    
    # Check environment variables
    echo "Checking environment variables in API container..."
    docker exec $API_CONTAINER env | grep -E 'OTLP|OTEL|TRACING'
    
    # Check if OpenTelemetry packages are installed
    echo "Checking if OpenTelemetry packages are installed in API container..."
    docker exec $API_CONTAINER pip freeze | grep -E 'opentelemetry'
fi

echo "--------------------------------"
echo "Verification complete"
