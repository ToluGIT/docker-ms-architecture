"""
Redis cache tracing initialization
"""
from .redis_tracing import instrument_redis, TracedRedis

__all__ = ['instrument_redis', 'TracedRedis']
