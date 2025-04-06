# config.py
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Get Redis configuration from environment variables
# Don't hardcode defaults in the code - rely on .env.dev or docker-compose
redis_password = os.getenv('REDIS_PASSWORD')
redis_host = os.getenv('REDIS_HOST', 'redis')  # Only hostname gets a default
redis_port = os.getenv('REDIS_PORT', '6379')   # Only port gets a default

# First check if there's a complete REDIS_URL provided
redis_url = os.getenv('REDIS_URL')

# If not, construct it from components, ensuring password is included if present
if not redis_url:
    if redis_password:
        redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"
    else:
        redis_url = f"redis://{redis_host}:{redis_port}/0"

# Log the URL (without exposing the password)
masked_url = redis_url.replace(f":{redis_password}@", ":***@") if redis_password else redis_url
print(f"Using Redis URL: {masked_url}")

# Initialize Limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url
)