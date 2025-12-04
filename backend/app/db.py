from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# Database URL (read from environment or fallback to default value)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://signage:signage_pass@db:5432/signage",
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Ensures the session is closed after the request is handled.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()