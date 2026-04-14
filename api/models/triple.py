"""
Triple Model - Auto-generated from OpenAPI
Generated at: 2026-04-13T00:52:56.714590
*** DO NOT MODIFY CORE LOGIC MANUALLY ***
Add custom methods below the # TODO: Custom methods 标记
# KAELIS-GENERATED
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

from . import Base


class Triple(Base):
    """
    知识图谱三元组
    
    Auto-generated from OpenAPI schema: Triple
    """
    __tablename__ = "triples"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(255), nullable=False)
    predicate = Column(String(255), nullable=False)
    object = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=True, default=0.95)
    metadata_ = Column(JSON, nullable=True)
    
    # Auto-generated timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # TODO: Define relationships and foreign keys
    # Example:
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # user = relationship("User", back_populates="triples")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            "subject": getattr(self, "subject"),
            "predicate": getattr(self, "predicate"),
            "object": getattr(self, "object"),
            "confidence": getattr(self, "confidence"),
            "metadata": getattr(self, "metadata_"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    # TODO: Custom methods - Add your business logic below
    
    def __repr__(self) -> str:
        return f"<Triple(id={self.id})>"
