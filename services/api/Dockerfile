# --- Build Stage ---
    FROM python:3.11-slim AS builder

    WORKDIR /app
    
    # Install build dependencies
    RUN apt-get update && \
        apt-get install -y --no-install-recommends gcc curl && \
        rm -rf /var/lib/apt/lists/*
    
    # Install Python dependencies
    COPY requirements.txt .
    RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt
    
    # --- Final Stage ---
    FROM python:3.11-slim
    
    # Create non-root user
    RUN groupadd -r appuser && useradd -r -g appuser appuser
    
    WORKDIR /app
    
    # Install runtime dependencies only
    RUN apt-get update && \
        apt-get install -y --no-install-recommends curl && \
        rm -rf /var/lib/apt/lists/*
    
    # Copy wheels from builder stage
    COPY --from=builder /app/wheels /app/wheels
    RUN pip install --no-cache /app/wheels/*
    
    # Copy application code
    COPY ./app /app/app
    
    # Set proper permissions
    RUN chown -R appuser:appuser /app
    USER appuser
    
    # Health check
    HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
        CMD curl -f http://localhost:8000/health || exit 1
    
    # Expose the port and start the application
    EXPOSE 8000
    ENV PYTHONPATH=/app
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]