# app/models/models.py

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, Text, ForeignKey
from sqlalchemy.sql import func
from ..db import Base
import uuid

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    provider = Column(String, nullable=False)

    priority = Column(Boolean, nullable=False, default=False)
    transcript = Column(Boolean, nullable=False, default=False)
    size_bytes = Column(Integer, nullable=False)
    duration_sec = Column(Float, nullable=False)
    price_cents = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="queued")
    progress = Column(Float, nullable=False, default=0.0)
    error = Column(Text, nullable=True)
    input_path = Column(Text, nullable=False)
    output_path = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    filename = Column(Text, nullable=True)
    output_url = Column(Text, nullable=True)
    token_used = Column(Text, ForeignKey("tokens.code"), nullable=True)


class Token(Base):
    __tablename__ = "tokens"

    code = Column(String, primary_key=True)
    discount_percent = Column(Integer, default=0)
    usage_limit = Column(Integer, default=1)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
