"""SQLAlchemy models for the Telegram AI Image Bot."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.db.database import Base


class User(Base):
    """User model representing a Telegram user."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    api_tokens_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_model: Mapped[str] = mapped_column(
        String(50), default="gpt-image-1.5", nullable=False
    )
    image_quality: Mapped[str] = mapped_column(
        String(10), default="medium", nullable=False
    )
    image_size: Mapped[str] = mapped_column(
        String(20), default="1024x1024", nullable=False
    )
    referrer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    tasks: Mapped[List["GenerationTask"]] = relationship(
        "GenerationTask", back_populates="user", lazy="selectin"
    )
    referrer: Mapped[Optional["User"]] = relationship(
        "User", remote_side=[id], foreign_keys=[referrer_id], lazy="selectin"
    )
    referrals: Mapped[List["User"]] = relationship(
        "User", back_populates="referrer", foreign_keys="User.referrer_id", lazy="selectin"
    )


class GenerationTask(Base):
    """Generation task model for image generation/editing requests."""
    
    __tablename__ = "generation_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "generate" | "edit"
    model: Mapped[str] = mapped_column(
        String(50), default="gpt-image-1.5", nullable=False
    )
    image_quality: Mapped[str] = mapped_column(
        String(10), default="medium", nullable=False
    )
    image_size: Mapped[str] = mapped_column(
        String(20), default="1024x1024", nullable=False
    )
    prompt: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    result_image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    result_file_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # "pending" | "processing" | "done" | "failed"
    tokens_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    api_tokens_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    images_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")


class Template(Base):
    """Template model for predefined prompt templates."""
    
    __tablename__ = "templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    prompt: Mapped[str] = mapped_column(String(2000), nullable=False)
    tokens_cost: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
