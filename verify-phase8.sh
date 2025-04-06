#!/bin/bash
# verify-phase8.sh

echo "Phase 8 Verification Script"
echo "==========================="

echo "1. Checking if services are running..."
curl -s http://localhost:8000/health > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ API service not running"
    exit 1
fi

curl -s http://localhost:9090/-/healthy > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Prometheus not running"
    exit 1
fi

curl -s http://localhost:3001/api/health > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Grafana not running"
    exit 1
fi

echo "✅ All required services are running"

echo "2. Generating test load..."
for i in {1..50}; do 
    curl -s http://localhost:8000/health > /dev/null
    printf "."
done
echo ""

echo "3. Checking SLO metrics in Prometheus..."
SLO_METRICS=$(curl -s "http://localhost:9090/api/v1/query?query=slo_info" | grep "slo_info")
if [ -z "$SLO_METRICS" ]; then
    echo "❌ SLO metrics not found in Prometheus"
else
    echo "✅ SLO metrics found in Prometheus"
fi

echo "4. Testing CLI commands..."
python3 scripts/slo_manager.py status --slo api_health

echo "5. Verification complete!"
echo "Now access the Grafana dashboard at: http://localhost:3001"
echo "Look for the 'Service Level Objectives' dashboard"
