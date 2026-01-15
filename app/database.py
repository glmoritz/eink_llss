"""
Database configuration and session management using SQLAlchemy.
"""

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

# Load environment variables
load_dotenv()

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://eink_root:eink123@localhost:5432/eink_llss"
)

# Schema name
SCHEMA = "eink_llss"

# Create engine with schema in search_path
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
    echo=os.getenv("DEBUG", "false").lower() == "true",
    connect_args={"options": f"-csearch_path={SCHEMA}"},
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables.

    Call this on application startup if you want to auto-create tables.
    For production, prefer using migrations (e.g., Alembic).
    """
    Base.metadata.create_all(bind=engine)
