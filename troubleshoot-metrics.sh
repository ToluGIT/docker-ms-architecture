#!/bin/bash

echo "Prometheus Metrics Troubleshooting"
echo "---------------------------------"

# Get API container details
API_CONTAINER=$(docker ps --filter "name=api" --format "{{.ID}}")
if [ -z "$API_CONTAINER" ]; then
    echo "❌ No API container found running"
    exit 1
fi

echo "✅ API container found: $API_CONTAINER"

# Get API container IP
API_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $API_CONTAINER)
echo "API container IP: $API_IP"

# Check if the API metrics endpoint is accessible from the Prometheus container
echo -e "\nTesting API metrics endpoint from Prometheus container..."
PROMETHEUS_CONTAINER=$(docker ps --filter "name=prometheus" --format "{{.ID}}")
if [ -z "$PROMETHEUS_CONTAINER" ]; then
    echo "❌ No Prometheus container found running"
else
    echo "✅ Prometheus container found: $PROMETHEUS_CONTAINER"
    echo "Trying to reach API metrics endpoint..."
    
    # Try with hostname
    echo "Trying with hostname 'api'..."
    docker exec $PROMETHEUS_CONTAINER wget -q --spider http://api:8000/metrics
    if [ $? -eq 0 ]; then
        echo "✅ API metrics endpoint is accessible via hostname 'api'"
    else
        echo "❌ Could not reach API metrics endpoint via hostname 'api'"
    fi
    
    # Try with IP
    echo "Trying with API IP address..."
    docker exec $PROMETHEUS_CONTAINER wget -q --spider http://$API_IP:8000/metrics
    if [ $? -eq 0 ]; then
        echo "✅ API metrics endpoint is accessible via IP $API_IP"
    else
        echo "❌ Could not reach API metrics endpoint via IP $API_IP"
    fi
    
    # Try localhost
    echo "Trying with localhost..."
    docker exec $PROMETHEUS_CONTAINER wget -q --spider http://localhost:8000/metrics
    if [ $? -eq 0 ]; then
        echo "✅ API metrics endpoint is accessible via localhost"
    else
        echo "❌ Could not reach API metrics endpoint via localhost"
    fi
fi

# Check networks
echo -e "\nChecking if API and Prometheus are on the same network..."
API_NETWORKS=$(docker inspect -f '{{range $key, $val := .NetworkSettings.Networks}}{{$key}} {{end}}' $API_CONTAINER)
PROMETHEUS_NETWORKS=$(docker inspect -f '{{range $key, $val := .NetworkSettings.Networks}}{{$key}} {{end}}' $PROMETHEUS_CONTAINER)

echo "API container networks: $API_NETWORKS"
echo "Prometheus container networks: $PROMETHEUS_NETWORKS"

# Check if they share any network
for api_net in $API_NETWORKS; do
    for prom_net in $PROMETHEUS_NETWORKS; do
        if [ "$api_net" = "$prom_net" ]; then
            echo "✅ API and Prometheus share network: $api_net"
            SHARED_NETWORK=1
        fi
    done
done

if [ -z "$SHARED_NETWORK" ]; then
    echo "❌ API and Prometheus do not share any networks"
fi

# Test API metrics endpoint directly
echo -e "\nTesting API metrics endpoint directly from host..."
curl -s http://localhost:8000/metrics > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ API metrics endpoint is accessible from host"
    echo "Sample of metrics:"
    curl -s http://localhost:8000/metrics | head -n 10
else
    echo "❌ Could not reach API metrics endpoint from host"
fi

# Check Prometheus targets
echo -e "\nChecking Prometheus targets..."
curl -s http://localhost:9090/api/v1/targets | grep -e "api" -e "job"

echo -e "\nTroubleshooting completed."