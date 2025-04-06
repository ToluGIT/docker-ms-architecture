#!/bin/bash

# Verify trace context propagation across services
echo "Verifying Trace Context Propagation"
echo "===================================="

# Generate a unique correlation ID for this test
CORRELATION_ID="test-$(date +%s)-$(( RANDOM % 1000 ))"
echo "Using correlation ID: $CORRELATION_ID"

# 1. Make a request to the API with trace context headers
echo -e "\n1. Testing API trace context extraction..."
API_RESPONSE=$(curl -s -D - http://localhost:8000/health \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -H "traceparent: 00-$(openssl rand -hex 16)-$(openssl rand -hex 8)-01")

# Extract the returned correlation ID and trace ID
RETURNED_CORRELATION_ID=$(echo "$API_RESPONSE" | grep -i "X-Correlation-ID" | awk '{print $2}' | tr -d '\r')
RETURNED_TRACE_ID=$(echo "$API_RESPONSE" | grep -i "X-Trace-ID" | awk '{print $2}' | tr -d '\r')

echo "Sent correlation ID: $CORRELATION_ID"
echo "Received correlation ID: $RETURNED_CORRELATION_ID"
echo "Received trace ID: $RETURNED_TRACE_ID"

if [ "$CORRELATION_ID" = "$RETURNED_CORRELATION_ID" ]; then
  echo "✅ Correlation ID was properly propagated through the API"
else
  echo "❌ Correlation ID was not properly propagated"
fi

if [ ! -z "$RETURNED_TRACE_ID" ]; then
  echo "✅ Trace ID was returned from the API"
else
  echo "❌ No trace ID returned from the API"
fi

# 2. Test the external API that uses Redis
echo -e "\n2. Testing cache propagation (API -> Redis)..."
EXTERNAL_RESPONSE=$(curl -s -D - http://localhost:8000/external-data \
  -H "X-Correlation-ID: $CORRELATION_ID-external" \
  -H "traceparent: 00-$(openssl rand -hex 16)-$(openssl rand -hex 8)-01")

# Extract the returned correlation ID and trace ID
EXTERNAL_CORRELATION_ID=$(echo "$EXTERNAL_RESPONSE" | grep -i "X-Correlation-ID" | awk '{print $2}' | tr -d '\r')
EXTERNAL_TRACE_ID=$(echo "$EXTERNAL_RESPONSE" | grep -i "X-Trace-ID" | awk '{print $2}' | tr -d '\r')

echo "Sent correlation ID: $CORRELATION_ID-external"
echo "Received correlation ID: $EXTERNAL_CORRELATION_ID"
echo "Received trace ID: $EXTERNAL_TRACE_ID"

# Check Jaeger for traces after a short delay
echo -e "\n3. Checking if traces appear in Jaeger..."
echo "Waiting for traces to be processed..."
sleep 3

# Use the Jaeger API to find traces with our correlation ID
TRACE_RESULTS=$(curl -s "http://localhost:16686/api/traces?service=api-service&tags=%7B%22correlation_id%22%3A%22$CORRELATION_ID%22%7D")
TRACE_COUNT=$(echo "$TRACE_RESULTS" | grep -o '"data":\[\{' | wc -l)

if [ $TRACE_COUNT -gt 0 ]; then
  echo "✅ Found traces in Jaeger with our correlation ID!"
else
  echo "❌ No traces found in Jaeger with our correlation ID"
fi

# 4. Test frontend to API propagation via Nginx
echo -e "\n4. Testing frontend to API propagation via Nginx..."
FRONTEND_RESPONSE=$(curl -s -D - http://localhost:3000/ \
  -H "X-Correlation-ID: $CORRELATION_ID-frontend" \
  -H "traceparent: 00-$(openssl rand -hex 16)-$(openssl rand -hex 8)-01")

# Check if we have CORS headers that allow trace context
CORS_HEADERS=$(echo "$FRONTEND_RESPONSE" | grep -i "Access-Control-Expose-Headers")
if [[ $CORS_HEADERS == *"traceparent"* ]]; then
  echo "✅ Nginx is configured to expose trace context headers"
else
  echo "❌ Nginx is not exposing trace context headers properly"
fi

echo -e "\nVerification complete!"
echo "===================================="
echo "For full trace visualization, visit:"
echo "http://localhost:16686/search?service=api-service"
