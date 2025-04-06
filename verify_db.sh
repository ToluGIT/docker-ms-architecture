#!/bin/bash

# Wait for the database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Run the test query
echo "Running test query..."
docker compose -f docker-compose.dev.yml exec db psql -U postgres -d app -f /tmp/test_db.sql

# Check if API can connect to the database
echo "Checking if API can connect to the database..."
curl http://localhost:8000/health

echo "Fetching users from API..."
curl http://localhost:8000/users

echo "Database verification complete!"