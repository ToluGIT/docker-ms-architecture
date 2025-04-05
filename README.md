# Docker Microservices Project

A comprehensive example of a production-ready microservices architecture using Docker, featuring a full-stack application with monitoring, caching, authentication, and automated tooling.


## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Production Environment](#production-environment)
- [CLI Management Tool](#cli-management-tool)
- [Monitoring & Observability](#monitoring--observability)
- [Authentication](#authentication)
- [Security Considerations](#security-considerations)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)


## Overview

This project demonstrates a modern approach to building, deploying, and managing microservices applications using Docker. It implements a functional system with:

- **Backend API**: FastAPI-based RESTful service with PostgreSQL for persistence
- **Frontend**: React application with responsive dashboard interface
- **Caching**: Redis for performance optimization and session management
- **Authentication**: JWT-based secure authentication
- **Monitoring**: Prometheus, Grafana, and Jaeger for metrics, visualization, and tracing
- **DevOps Tools**: CLI utility for managing the entire application lifecycle

This project serves as both a learning resource and a practical template for production-ready microservices deployments.

## System Architecture

The application follows a layered microservices architecture:

1. **Client Layer**: Browser-based access to the application
2. **Services Layer**: Frontend (React+Nginx) and Backend (FastAPI) services
3. **Data Layer**: PostgreSQL for persistent storage and Redis for caching
4. **Monitoring Layer**: Prometheus, Grafana, and Jaeger for observability
5. **Management Layer**: CLI tool for operations and maintenance

Services communicate over defined Docker networks with proper isolation between components.

![Dockerimage01](https://github.com/user-attachments/assets/7e8e299e-6efe-46da-a6dd-36675b13dc66)

## Key Features

- **Separation of Concerns**: Each service has a specific responsibility and can be developed/scaled independently
- **Environment-Specific Configurations**: Separate dev and prod configurations with appropriate optimizations
- **Security**: Non-root users, network isolation, secrets management, and secure defaults
- **Observability**: Comprehensive monitoring and logging for all services
- **Scalability**: Services can be scaled independently based on demand
- **Developer Experience**: Hot-reloading in development, easy-to-use CLI

## Prerequisites

- Docker (version 20.10 or later recommended)
- Docker Compose (version 2.x or later)
- Python 3.8+ (for the CLI tool)
- Git

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/yourusername/docker-microservices-project.git
cd docker-microservices-project
```

### Install CLI Dependencies

```bash
pip install rich requests
```

### Generate Secrets for Development

```bash
# Generate development secrets (or create .env.dev file manually)
python generate_secrets.py --all > .env.dev
```

### Start the Application (Development Mode)

```bash
./microservices  --env dev start
```

### Access the Application

- Frontend: http://localhost:3000
- API: http://localhost:8000

## Development Environment

The development environment is optimized for iteration and debugging:

- **Volume Mounting**: Code changes are reflected without rebuilding containers
- **Hot Reloading**: Frontend and API services automatically reload on code changes
- **Debug Logs**: More verbose logging for troubleshooting
- **Default Credentials**:
  - Database: `postgres`/`securedbpassword`
  - Redis: Password `secureredispassword`
  - API Admin: Username `admin`/Password `admin123`

### Start Development Environment

```bash
./microservices  --env dev build
./microservices  --env dev start
```

## Production Environment

The production environment is optimized for security, performance, and reliability:

- **Multi-Stage Builds**: Optimized Docker images with minimal dependencies
- **Resource Limits**: CPU and memory constraints to prevent resource exhaustion
- **Health Checks**: Automatic detection and recovery from failures
- **Secure Configuration**: No default credentials, required environment variables

### Prepare for Production

```bash
# Generate secure secrets for production
python generate_secrets.py --all > .env.prod

# Edit .env.prod to customize settings if needed
```

### Start Production Environment

```bash
./microservices  --env prod build
./microservices  --env prod start
```

## CLI Management Tool

The project includes a powerful CLI tool for managing the application:

```bash
# Show status of all services
./microservices status

# Start specific services
./microservices start --services api frontend

# View logs
./microservices logs --service api

# Run security checks
./microservices security-check

# Check network connectivity between services
./microservices network-check

# Generate dependency graph
./microservices dependency-graph


# Start monitoring stack
./microservices start-monitoring
```

## Monitoring & Observability

### Start Monitoring Stack

```bash
./microservices start-monitoring
```

### Access Monitoring Dashboards

- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090
- Jaeger Tracing: http://localhost:16686

### Available Metrics and Dashboards

- API endpoints request counts
- Container memory and CPU usage
- Success rate

## Authentication

The application uses JWT (JSON Web Tokens) for authentication:

1. **Login**: POST to `/auth/token` with username/password to receive a token
2. **Authenticated Requests**: Include the token in the Authorization header
3. **Token Expiration**: Tokens expire after 30 minutes by default

Default user accounts (development only):
- Admin: `admin`/`admin123`

## Security Considerations

- Database and Redis services are not exposed externally
- Non-root users are used in Docker containers
- Secrets are managed through environment variables
- Proper network segmentation between services
- Rate limiting to prevent abuse
- Input validation to prevent injection attacks

For production, ensure you:
1. Change all default passwords
2. Use proper secrets management
3. Enable TLS/SSL for all public endpoints
4. Regularly scan for vulnerabilities (`./microservices scan`)

## Project Structure

```
docker-microservices-project/
├── services/              # Application services
│   ├── api/               # FastAPI backend
│   ├── frontend/          # React frontend
│   ├── db/                # PostgreSQL database
│   └── redis/             # Redis cache
├── monitoring/            # Monitoring configuration
│   ├── prometheus/
│   └── grafana/
├── scripts/               # Management scripts
│   └── cli.py             # CLI management tool
├── docker-compose.yml     # Base Docker Compose config
├── docker-compose.dev.yml # Development overrides
├── docker-compose.prod.yml # Production overrides
└── README.md
```

## Troubleshooting

### Common Issues

1. **Services won't start**
   - Check logs: `./microservices logs --service <service_name>`
   - Verify environment variables in `.env.dev` or `.env.prod`
   - Ensure ports are not already in use

2. **Authentication failures**
   - Verify database is running and initialized
   - Check Redis connection for session storage
   - Ensure JWT secret is properly set

3. **Frontend can't connect to API**
   - Check CORS settings and allowed origins
   - Verify network connectivity between containers
   - Check Nginx proxy configuration

### Diagnostic Commands

```bash
# Check service health
./microservices status

# Test Redis connectivity
./check-redis.sh

# Verify database
./verify_db.sh

# Troubleshoot metrics collection
./troubleshoot-metrics.sh

# Check network between services
./microservices network-check
```

---

This project demonstrates Docker microservices best practices and provides a template for building real-world applications.
