"""
Kaelis Database Models
Auto-generated from OpenAPI specification
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models for Alembic/SQLAlchemy metadata
try:
    from .triple import Triple
except ImportError:
    pass  # Model not yet generated


__all__ = [
    "Base",
    "Triple",
]
