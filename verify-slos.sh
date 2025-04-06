#!/bin/bash
# verify-slos.sh

echo "SLO Verification Tool"
echo "====================="

# Check if monitoring and tracing are running
echo "1. Checking infrastructure..."
PROMETHEUS_RUNNING=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy)
if [ "$PROMETHEUS_RUNNING" != "200" ]; then
    echo "❌ Prometheus is not running on port 9090"
    echo "Start monitoring with: ./microservices start-monitoring"
    exit 1


echo "✅ Monitoring infrastructure is running"

# Check for SLO metrics
echo "2. Checking SLO metrics in Prometheus..."
SLO_METRICS=$(curl -s "http://localhost:9090/api/v1/query" --data-urlencode "query=slo_info")
SLO_INFO=$(echo $SLO_METRICS | grep -o '"slo_info"')

if [ -z "$SLO_INFO" ]; then
    echo "❌ SLO metrics not found in Prometheus"
    echo "Ensure you've deployed the updated trace_metrics.py file"
    exit 1
fi

echo "✅ SLO metrics found in Prometheus"

# Generate some test load
echo "3. Generating test traffic to populate SLO metrics..."
echo "   - Health endpoint (affects api_health SLO)"
for i in {1..50}; do
    curl -s "http://localhost:8000/health" > /dev/null
    printf "."
done
echo ""

echo "   - External data endpoint (affects external_data SLO)"
for i in {1..20}; do
    curl -s "http://localhost:8000/external-data" > /dev/null
    printf "."
done
echo ""

echo "   - Users endpoint (affects data_access SLO)"
for i in {1..15}; do
    curl -s "http://localhost:8000/users/" > /dev/null
    printf "."
done
echo ""

# Wait for metrics to be collected
echo "4. Waiting for metrics to be processed..."
sleep 10

# Check SLO compliance
echo "5. Checking SLO compliance metrics..."
SLO_COMPLIANCE=$(curl -s "http://localhost:9090/api/v1/query" --data-urlencode "query=slo_compliance_ratio")
COMPLIANCE_FOUND=$(echo $SLO_COMPLIANCE | grep -o '"slo_compliance_ratio"')

if [ -z "$COMPLIANCE_FOUND" ]; then
    echo "❌ SLO compliance metrics not found"
    echo "Check the Prometheus logs for errors"
else
    echo "✅ SLO compliance metrics are being recorded"
    echo ""
    echo "Try these commands to view SLO status:"
    echo "  - ./microservices slo status                 # View all SLOs"
    echo "  - ./microservices slo status --slo api_health # View specific SLO"
    echo "  - ./microservices slo alerts                 # View SLO alerts"
    echo "  - ./microservices slo test --endpoint /health # Test an endpoint"
    echo ""
    echo "Also check the SLO dashboard in Grafana:"
    echo "  http://localhost:3001/d/service-level-objectives/service-level-objectives"
fi
