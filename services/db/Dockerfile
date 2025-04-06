FROM postgres:13-alpine

# Set environment variables for PostgreSQL
# ENV POSTGRES_USER=postgres
# ENV POSTGRES_PASSWORD=postgres
# ENV POSTGRES_DB=app

# Copy initialization scripts
COPY ./init/ /docker-entrypoint-initdb.d/

# Add health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD pg_isready -U postgres || exit 1