import os
import secrets
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class CredentialManager:
    """Centralized credential management for the microservices application"""
    
    @staticmethod
    def get_secret(name: str, default: Optional[str] = None, 
                  auto_generate: bool = False, length: int = 32,
                  log_warning: bool = True) -> str:
        """Get a secret from environment variables or mounted secrets"""
        # Try environment variable
        value = os.getenv(name)
        
        # Try secrets file (Docker/K8s secrets)
        if not value and os.path.exists(f"/run/secrets/{name.lower()}"):
            with open(f"/run/secrets/{name.lower()}", "r") as f:
                value = f.read().strip()
        
        # Auto-generate if configured
        if not value and auto_generate:
            value = secrets.token_hex(length)
            if log_warning:
                logger.warning(f"Auto-generated {name} secret. This is not secure for production!")
        
        # Fall back to default
        if not value:
            if default and log_warning:
                logger.warning(f"Using default value for {name}. This is not secure for production!")
            value = default
            
        return value
    
    @staticmethod
    def get_database_url() -> str:
        """Build a database URL from components or return the complete URL"""
        # Check for complete URL first
        db_url = CredentialManager.get_secret("DATABASE_URL", 
                                             default="postgresql://postgres:postgres@db:5432/app",
                                             log_warning=True)
        
        # If specific components are provided, build the URL from them
        db_user = CredentialManager.get_secret("DB_USER", default="postgres", log_warning=False)
        db_password = CredentialManager.get_secret("DB_PASSWORD", default="postgres", log_warning=False)
        db_host = CredentialManager.get_secret("DB_HOST", default="db", log_warning=False)
        db_port = CredentialManager.get_secret("DB_PORT", default="5432", log_warning=False)
        db_name = CredentialManager.get_secret("DB_NAME", default="app", log_warning=False)
        
        # If any specific component was set, rebuild the URL
        if os.getenv("DB_USER") or os.getenv("DB_PASSWORD") or os.getenv("DB_HOST") or \
           os.getenv("DB_PORT") or os.getenv("DB_NAME"):
            db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            
        return db_url
    
    @staticmethod
    def get_redis_url() -> str:
        """Build a Redis URL from components or return the complete URL"""
        # Check for complete URL first
        redis_url = CredentialManager.get_secret("REDIS_URL", 
                                               default="redis://redis:6379",
                                               log_warning=True)
        
        # If specific components are provided, build the URL
        redis_host = CredentialManager.get_secret("REDIS_HOST", default="redis", log_warning=False)
        redis_port = CredentialManager.get_secret("REDIS_PORT", default="6379", log_warning=False)
        redis_password = CredentialManager.get_secret("REDIS_PASSWORD", default=None, log_warning=False)
        
        # If any component was explicitly set, rebuild the URL
        if os.getenv("REDIS_HOST") or os.getenv("REDIS_PORT") or os.getenv("REDIS_PASSWORD"):
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}"
            else:
                redis_url = f"redis://{redis_host}:{redis_port}"
                
        return redis_url
    
    @staticmethod
    def get_jwt_settings() -> dict:
        """Get all JWT-related settings"""
        return {
            "secret_key": CredentialManager.get_secret(
                "JWT_SECRET_KEY",
                default="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
                auto_generate=True
            ),
            "algorithm": CredentialManager.get_secret("JWT_ALGORITHM", default="HS256"),
            "access_token_expire_minutes": int(CredentialManager.get_secret(
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", default="30"
            )),
        }