I# Nexa API - Microservices Architecture with Docker

A microservices architecture showcasing best practices for container-based applications, featuring monitoring, tracing, authentication.

**[Read the detailed project walkthrough on Medium](https://medium.com/@tolubanji/from-zero-to-building-a-microservice-platform-a94e0a385c66)**

![Nexa API Architecture](https://github.com/user-attachments/assets/7e8e299e-6efe-46da-a6dd-36675b13dc66)

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Technical Highlights](#technical-highlights)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Monitoring & Observability](#monitoring--observability)
- [Authentication & Security](#authentication--security)
- [Project Structure](#project-structure)
- [CLI Management Tool](#cli-management-tool)
- [Troubleshooting](#troubleshooting)

## Overview

Nexa API demonstrates an approach to building resilient, observable, and secure microservices using Docker. It implements a functional system featuring:

- **FastAPI Backend**: RESTful API with PostgreSQL persistence and Redis caching
- **React Frontend**: Responsive dashboard with JWT authentication
- **Monitoring**: Prometheus metrics, Grafana dashboards, and distributed tracing
- **Advanced Observability**: OpenTelemetry integration with trace propagation across services
- **Service Level Objectives**: Defined SLOs with monitoring and compliance tracking
- **Production-Ready Security**: Authentication, rate limiting, and secure defaults
- **DevOps Automation**: CLI utility for the application lifecycle

This project serves as both a learning resource and a practical template for implementing microservices in environments.

## System Architecture

The architecture follows a layered microservices design with proper separation of concerns:

### Service Layers

1. **Frontend Layer**: React application with OpenTelemetry tracing, served via Nginx
2. **API Layer**: FastAPI service with JWT auth, rate limiting, and distributed tracing
3. **Data Layer**: 
   - PostgreSQL for persistent storage
   - Redis for caching and session management
4. **Monitoring Layer**:
   - Prometheus for metrics collection
   - Grafana for visualization
   - Jaeger for distributed tracing

### Network Architecture

Services communicate over isolated Docker networks with proper segmentation:
- `app-network`: Core application communication
- `monitoring-network`: Metrics and monitoring tools
- `tracing-network`: Distributed tracing data flow

## Key Features

### Production-Ready Authentication
- JWT token-based authentication with secure defaults
- Configurable token expiration and refresh
- Password hashing with bcrypt
- Integration with Redis for distributed session storage

### Comprehensive Monitoring
- Real-time metrics collection across all services
- Custom dashboards for system performance
- Container resource utilization tracking
- Service Level Objectives (SLOs) with alerting

### Distributed Tracing
- End-to-end request tracing across services
- Performance bottleneck identification
- Error correlation and root cause analysis
- Custom trace attributes and span annotations

### Caching Layer
- Redis-backed caching for performance optimization
- Instrumented cache operations for observability
- Automatic cache invalidation strategies
- Cache hit/miss metrics for optimization

### Resilient Database Access
- Repository pattern for data access abstraction
- Connection pooling for performance optimization
- Instrumented database operations
- Automatic retry mechanisms for transient failures

### DevOps Integration
- Comprehensive CLI tooling
- Network health checks
- Security scanning
- Environment-specific configurations

## Technical Highlights

### OpenTelemetry Integration
- Context propagation across service boundaries
- Custom trace attributes for business logic
- Correlation IDs for request tracking
- Integration with Jaeger for visualization


### Security Features
- Rate limiting to prevent abuse
- Origin validation and CORS protection
- Non-root container users
- Network segmentation and isolation

### Optimized Docker Configuration
- Multi-stage builds for smaller images
- Environment-specific optimizations
- Health checks for automatic recovery
- Resource limits to prevent resource exhaustion

## Getting Started

### Prerequisites

- Docker (version 20.10 or later)
- Docker Compose (version 2.x or later)
- Python 3.8+ (for the CLI tool)
- Git

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd docker-ms-architecture

# Install CLI dependencies
pip install rich requests

# Start development environment
./microservices --env dev start

# Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/api-docs
```

### Default Credentials

- **API Admin**: Username `admin` / Password `admin123`

## Development Workflow

### Development Environment

```bash
# Build services for development
./microservices --env dev build

# Start services in development mode
./microservices --env dev start

# View service status
./microservices --env dev status

# View logs for specific service
./microservices --env dev logs --service api
```

Development mode features:
- Code hot-reloading
- Volume mounting for live code changes
- Enhanced logging and debugging
- Default credentials and sample data

### Testing

```bash
# Run all tests
./microservices --env dev test

# Run specific test path
./microservices --env dev test --test-path services/api/tests/test_api.py
```

### Production Environment

```bash
# Build for production
./microservices --env prod build

# Start production environment
./microservices --env prod start
```

Production mode features:
- Multi-stage Docker builds
- Optimized container images
- Resource limits and constraints
- Enhanced security settings

## Monitoring & Observability

### Starting Monitoring Stack

```bash
./microservices start-monitoring
```

### Access Dashboards

- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger Tracing**: http://localhost:16686

### Available Metrics

- API request counts and latencies
- Container memory and CPU usage
- Service Level Objective compliance
- Cache hit/miss ratios
- Database operation timing
- Custom business metrics

### Distributed Tracing

```bash
# Start tracing system
./microservices start-tracing

# View trace summary
./microservices trace-summary

# Query specific traces
./microservices query-traces --service api --limit 20
```

## Authentication & Security

### Authentication Flow

1. **Login**: POST to `/auth/token` with username/password
2. **Token Usage**: Include JWT in Authorization header
3. **Protected Resources**: Access API endpoints with valid token

### Security Features

- Rate limiting to prevent abuse
- Input validation to prevent injection attacks
- Non-root Docker container users
- Network isolation between services
- CORS protection with origin validation

### Security Scanning

```bash
# Scan Docker images for vulnerabilities
./microservices scan

# Perform security checks
./microservices security-check
```

## CLI Management Tool

The project includes a CLI tool for managing the application:

```bash
# Show status of all services
./microservices status

# View logs
./microservices logs --service api

# Run security checks
./microservices security-check

# Check network connectivity
./microservices network-check

# Generate dependency graph
./microservices dependency-graph

# Start monitoring stack
./microservices start-monitoring

# Trace analysis
./microservices trace-summary --days 1

# Performance benchmarks
./microservices benchmark --endpoint /health --requests 100
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

# Check network between services
./microservices network-check
```