# --- Build Stage ---
FROM node:18-alpine AS build

WORKDIR /app

# Install jq for JSON manipulation
RUN apk add --no-cache jq

# Install dependencies
COPY package.json ./
# Remove package-lock.json reference if it doesn't exist
RUN npm install

# Add OpenTelemetry packages
COPY package.opentelemetry.json ./
RUN cat package.opentelemetry.json | jq -s '.[0] * .[1]' package.json - > package.combined.json && \
    mv package.combined.json package.json && \
    npm install

# Copy source code and build
COPY . .
# Set environment variables for the build
ARG REACT_APP_OTEL_ENABLED=true
ARG REACT_APP_SERVICE_NAME=frontend-service
RUN npm run build

# --- Production Stage ---
FROM nginx:alpine

# Copy custom entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy built app from the build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy custom NGINX configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set environment variables for tracing
ENV REACT_APP_OTEL_ENABLED=true
ENV REACT_APP_SERVICE_NAME=frontend-service
ENV REACT_APP_OTEL_ENDPOINT=/api/v1/traces

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# Start with our custom entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
