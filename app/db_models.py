"""
SQLAlchemy ORM models for LLSS database.
"""

from datetime import datetime, timezone

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
from sqlalchemy.orm import relationship

from database import Base, SCHEMA


class HLSSType(Base):
    """
    Registry of available HLSS backends.

    Each HLSS type represents a specific application backend (e.g., lichess, homeassistant).
    Admins register HLSS types before creating instances of that type.
    """

    __tablename__ = "hlss_types"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    type_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    base_url = Column(
        String(500), nullable=False
    )  # e.g., https://lichess-hlss.example/api
    auth_token = Column(
        String(255), nullable=True
    )  # Token LLSS uses to authenticate with HLSS

    # Display defaults (can be overridden by device capabilities)
    default_width = Column(Integer, nullable=True)
    default_height = Column(Integer, nullable=True)
    default_bit_depth = Column(Integer, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

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
    instances = relationship("Instance", back_populates="hlss_type")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "type_id": self.type_id,
            "name": self.name,
            "description": self.description,
            "base_url": self.base_url,
            "default_width": self.default_width,
            "default_height": self.default_height,
            "default_bit_depth": self.default_bit_depth,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Device(Base):
    """Physical e-Ink device (ESP32-based)."""

    __tablename__ = "devices"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
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
    current_frame_id = Column(String(50), nullable=True)
    active_instance_id = Column(String(50), nullable=True)

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
            "device_id": self.device_id,
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
            "current_frame_id": self.current_frame_id,
            "active_instance_id": self.active_instance_id,
        }


class Instance(Base):
    """HLSS instance managed by LLSS."""

    __tablename__ = "instances"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    access_token = Column(String(64), nullable=True, index=True)

    # HLSS type reference (optional for backwards compatibility)
    hlss_type_id = Column(
        String(50),
        ForeignKey(f"{SCHEMA}.hlss_types.type_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # HLSS initialization state
    hlss_initialized = Column(Boolean, default=False, nullable=False)
    hlss_ready = Column(Boolean, default=False, nullable=False)
    needs_configuration = Column(Boolean, default=False, nullable=False)
    configuration_url = Column(String(500), nullable=True)

    # Display configuration (copied from device or HLSS type defaults)
    display_width = Column(Integer, nullable=True)
    display_height = Column(Integer, nullable=True)
    display_bit_depth = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    initialized_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    frames = relationship("Frame", back_populates="instance")
    hlss_type = relationship("HLSSType", back_populates="instances")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "instance_id": self.instance_id,
            "name": self.name,
            "type": self.type,
            "hlss_type_id": self.hlss_type_id,
            "hlss_initialized": self.hlss_initialized,
            "hlss_ready": self.hlss_ready,
            "needs_configuration": self.needs_configuration,
            "configuration_url": self.configuration_url,
            "display": (
                {
                    "width": self.display_width,
                    "height": self.display_height,
                    "bit_depth": self.display_bit_depth,
                }
                if self.display_width
                else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "initialized_at": (
                self.initialized_at.isoformat() if self.initialized_at else None
            ),
        }


class Frame(Base):
    """Rendered frame data."""

    __tablename__ = "frames"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    frame_id = Column(String(50), unique=True, nullable=False, index=True)
    instance_id = Column(
        String(50),
        ForeignKey(f"{SCHEMA}.instances.instance_id", ondelete="SET NULL"),
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
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        String(50),
        ForeignKey(f"{SCHEMA}.devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_id = Column(
        String(50),
        ForeignKey(f"{SCHEMA}.instances.instance_id", ondelete="CASCADE"),
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
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        String(50),
        ForeignKey(f"{SCHEMA}.devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_id = Column(String(50), nullable=True)

    # Event data
    button = Column(String(20), nullable=False)
    event_type = Column(String(20), nullable=False)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
