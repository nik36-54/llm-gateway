"""Database models for cost tracking and API keys."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class APIKey(Base):
    """API Key model for authentication and rate limiting."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    rate_limit_per_minute = Column(Integer, nullable=False, default=60)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    cost_records = relationship("CostRecord", back_populates="api_key")
    request_logs = relationship("RequestLog", back_populates="api_key")


class CostRecord(Base):
    """Cost record for tracking LLM usage and costs."""

    __tablename__ = "cost_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(
        UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False, index=True
    )
    request_id = Column(String(255), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    tokens_in = Column(Integer, nullable=False)
    tokens_out = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    api_key = relationship("APIKey", back_populates="cost_records")

    __table_args__ = (
        Index("idx_cost_records_api_key_created", "api_key_id", "created_at"),
        Index("idx_cost_records_provider_model", "provider", "model"),
    )


class RequestLog(Base):
    """Request log for detailed tracing and debugging."""

    __tablename__ = "request_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(255), nullable=False, index=True)
    api_key_id = Column(
        UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False, index=True
    )
    task = Column(String(50), nullable=True)
    budget = Column(String(20), nullable=True)
    latency_sensitive = Column(Boolean, nullable=True)
    provider_used = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # success, failure, fallback
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    api_key = relationship("APIKey", back_populates="request_logs")

    __table_args__ = (Index("idx_request_logs_request_id", "request_id"),)

