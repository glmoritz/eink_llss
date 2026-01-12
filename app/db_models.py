"""
SQLAlchemy ORM models for LLSS database.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Device(Base):
    """Physical e-Ink device (ESP32-based)."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True, default=uuid.uuid4
    )
    device_secret = Column(String(64), nullable=False)
    access_token = Column(String(64), nullable=False, index=True)
    hardware_id = Column(String(100), unique=True, nullable=False, index=True)
    firmware_version = Column(String(50), nullable=False)

    # Display capabilities
    display_width = Column(Integer, nullable=False)
    display_height = Column(Integer, nullable=False)
    display_bit_depth = Column(Integer, nullable=False, default=4)
    display_partial_refresh = Column(Boolean, nullable=False, default=False)

    # Current state
    current_frame_id = Column(UUID(as_uuid=True), nullable=True)
    active_instance_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "device_id": str(self.device_id),
            "device_secret": self.device_secret,
            "access_token": self.access_token,
            "hardware_id": self.hardware_id,
            "firmware_version": self.firmware_version,
            "display": {
                "width": self.display_width,
                "height": self.display_height,
                "bit_depth": self.display_bit_depth,
                "partial_refresh": self.display_partial_refresh,
            },
            "current_frame_id": (
                str(self.current_frame_id) if self.current_frame_id else None
            ),
            "active_instance_id": (
                str(self.active_instance_id) if self.active_instance_id else None
            ),
        }


class Instance(Base):
    """HLSS instance managed by LLSS."""

    __tablename__ = "instances"

    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True, default=uuid.uuid4
    )
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    access_token = Column(String(64), nullable=True, index=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    frames = relationship("Frame", back_populates="instance")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "instance_id": str(self.instance_id),
            "name": self.name,
            "type": self.type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Frame(Base):
    """Rendered frame data."""

    __tablename__ = "frames"

    id = Column(Integer, primary_key=True, index=True)
    frame_id = Column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True, default=uuid.uuid4
    )
    instance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("instances.instance_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Frame data
    data = Column(LargeBinary, nullable=False)
    hash = Column(String(64), nullable=False)

    # Metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    instance = relationship("Instance", back_populates="frames")


class DeviceInstanceMap(Base):
    """Mapping between devices and instances."""

    __tablename__ = "device_instance_map"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("instances.instance_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class InputEvent(Base):
    """Input events for logging/debugging."""

    __tablename__ = "input_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_id = Column(UUID(as_uuid=True), nullable=True)

    # Event data
    button = Column(String(20), nullable=False)
    event_type = Column(String(20), nullable=False)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
