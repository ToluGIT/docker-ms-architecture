FROM redis:alpine

# Copy configuration file and startup script
COPY redis.conf /usr/local/etc/redis/redis.conf
COPY docker-entrypoint.sh /usr/local/bin/

# Create volume directory with proper permissions
RUN mkdir -p /data && chown redis:redis /data

# Make startup script executable
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Fix permissions for redis user on config directory
RUN chown -R redis:redis /usr/local/etc/redis

# Set health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 CMD redis-cli ping || exit 1

# Set entrypoint to our custom script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
