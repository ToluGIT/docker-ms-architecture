import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.security.credentials import CredentialManager


# Get database connection parameters securely
DATABASE_URL = CredentialManager.get_database_url()

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()# Add these imports
try:
    from .db_tracing import instrument_database, enable_statement_tracing
    from .db_tracing.metrics import enable_db_metrics
    tracing_available = True
except ImportError:
    tracing_available = False

# Add after creating the engine (after the 'engine = create_engine' line)
# Initialize database tracing if available
if tracing_available:
    instrument_database(engine)
    enable_statement_tracing(engine)
    enable_db_metrics(engine)
