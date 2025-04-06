#!/bin/bash

echo "Verifying Tracing Infrastructure"
echo "--------------------------------"

# Check if Jaeger is running
JAEGER_CONTAINER=$(docker ps --filter "name=jaeger" --format "{{.Names}}")
if [ -z "$JAEGER_CONTAINER" ]; then
    echo "❌ Jaeger container is not running"
    echo "Start it with: ./microservices start-tracing"
    exit 1
fi

echo "✅ Jaeger container is running: $JAEGER_CONTAINER"

# Check if Jaeger UI is accessible
echo "Checking Jaeger UI..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:16686 | grep 200 > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Jaeger UI is accessible at: http://localhost:16686"
else
    echo "❌ Cannot access Jaeger UI. Check if port 16686 is exposed properly."
    exit 1
fi

# Check if collector endpoint is accessible
echo "Checking collector endpoints..."
# Test OTLP gRPC port
nc -z localhost 4317
if [ $? -eq 0 ]; then
    echo "✅ OTLP gRPC endpoint is accessible on port 4317"
else
    echo "❌ Cannot access OTLP gRPC endpoint on port 4317"
fi

# Test OTLP HTTP port
nc -z localhost 4318
if [ $? -eq 0 ]; then
    echo "✅ OTLP HTTP endpoint is accessible on port 4318"
else
    echo "❌ Cannot access OTLP HTTP endpoint on port 4318"
fi

# Check network connectivity
echo "Checking network connectivity..."
API_CONTAINER=$(docker ps --filter "name=api" --format "{{.Names}}")
if [ -n "$API_CONTAINER" ]; then
    echo "Testing connectivity from API container to Jaeger..."
    docker exec $API_CONTAINER ping -c 1 jaeger-tracing > /dev/null
    if [ $? -eq 0 ]; then
        echo "✅ API container can reach Jaeger"
    else
        echo "❌ API container cannot reach Jaeger. Check network configuration."
    fi
else
    echo "⚠️ API container not found. Cannot test connectivity."
fi

echo "--------------------------------"
echo "✅ Tracing infrastructure verification complete"
echo "Note: No traces will appear until services are instrumented (Phase 2)"
