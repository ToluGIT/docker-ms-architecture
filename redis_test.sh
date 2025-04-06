#!/bin/bash

echo "Testing Redis connectivity and functionality..."

# Check if Redis is running
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" ping
if [ $? -ne 0 ]; then
    echo "Redis is not responding to PING. Please check the service."
    exit 1
fi

# Test basic operations
echo "Testing basic Redis operations..."

# Set a key
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" set test_key "Hello from Redis!"
if [ $? -ne 0 ]; then
    echo "Failed to set a key in Redis."
    exit 1
fi

# Get the key
echo "Reading test key value:"
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" get test_key

# Test persistence
echo "Testing persistence configuration..."
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" config get appendonly
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" config get dir
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" config get dbfilename

# Test memory settings
echo "Checking memory settings..."
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword"  config get maxmemory
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" config get maxmemory-policy

echo "Redis test completed successfully!"
