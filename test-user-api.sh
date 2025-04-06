#!/bin/bash

# This script helps troubleshoot the user creation API

# Get token from user input
echo "Enter your JWT token (from browser localStorage):"
read TOKEN

# Print the token (partially)
echo "Using token: ${TOKEN:0:20}..."

# Test the API directly to understand the expected schema
echo -e "\nChecking API schema with a test call..."
docker compose -f docker-compose.prod.yml exec api curl -v http://localhost:8000/users/ \
  -H "Authorization: Bearer $TOKEN"

# Try to create a user with basic data
echo -e "\nTesting user creation with basic data..."
docker compose -f docker-compose.prod.yml exec api curl -v -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }' \
  http://localhost:8000/users/

# Try to create a user with more complete data
echo -e "\nTesting user creation with complete data..."
docker compose -f docker-compose.prod.yml exec api curl -v -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "testuser2",
    "email": "test2@example.com",
    "password": "password123",
    "is_active": true
  }' \
  http://localhost:8000/users/

echo -e "\nDone with API testing"
