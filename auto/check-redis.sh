#!/bin/bash

echo "Checking Redis connectivity from API container..."

# Test Redis connection using Python from API container
docker compose -f docker-compose.dev.yml exec api python3 -c "
import redis
import os
import re
from urllib.parse import urlparse

try:
    # First get password from environment variables
    redis_password = None
    
    # Try to get password from REDIS_URL
    redis_url = os.getenv('REDIS_URL')
    if redis_url:
        # Parse the URL to extract password
        try:
            parsed_url = urlparse(redis_url)
            # Extract password from auth part
            auth_part = parsed_url.netloc.split('@')[0]
            if ':' in auth_part:
                redis_password = auth_part.split(':')[1]
        except Exception as e:
            print(f'Failed to parse REDIS_URL: {e}')
    
    # If password not found in REDIS_URL, try REDIS_PASSWORD
    if not redis_password:
        redis_password = os.getenv('REDIS_PASSWORD')
    
    # Connect to Redis with password if available
    if redis_password:
        r = redis.Redis(host='redis', port=6379, db=0, password=redis_password)
    else:
        r = redis.Redis(host='redis', port=6379, db=0)
        
    pong = r.ping()
    print(f'Redis connection test: {pong}')
    print('Redis is working correctly!')
except Exception as e:
    print(f'Error connecting to Redis: {e}')
    print('Attempting to diagnose the issue...')
    
    # Check network connectivity
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('redis', 6379))
        print('Network connection to redis:6379 successful')
        s.close()
    except Exception as e:
        print(f'Network connection failed: {e}')
    
    # Check environment variables
    import os
    print(f'REDIS_URL environment variable: {os.getenv(\"REDIS_URL\", \"Not set\")}')
    print(f'REDIS_PASSWORD environment variable: {\"Set\" if os.getenv(\"REDIS_PASSWORD\") else \"Not set\"}')
"

# Test direct network connectivity between containers
echo -e "\nChecking network connectivity between containers..."
docker compose -f docker-compose.dev.yml exec api ping -c 3 redis

# Show Redis container information
echo -e "\nRedis container details:"
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" info server | grep redis_version
docker compose -f docker-compose.dev.yml exec redis redis-cli -a "secureredispassword" info clients
