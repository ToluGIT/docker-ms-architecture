#!/bin/sh
set -e

# Replace ${REDIS_PASSWORD} with the actual environment variable in redis.conf
if [ -n "$REDIS_PASSWORD" ]; then
  # Replace any existing requirepass line or add it if not present
  if grep -q "^requirepass" /usr/local/etc/redis/redis.conf; then
    sed -i "s/^requirepass.*/requirepass $REDIS_PASSWORD/" /usr/local/etc/redis/redis.conf
  else
    echo "requirepass $REDIS_PASSWORD" >> /usr/local/etc/redis/redis.conf
  fi
  echo "Redis password has been configured."
else
  echo "Warning: REDIS_PASSWORD environment variable is not set. Redis will not use password authentication."
fi

# Launch Redis with the updated configuration
exec redis-server /usr/local/etc/redis/redis.conf

