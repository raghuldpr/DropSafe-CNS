import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """DropSafe User Account Model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled', 'pending')",
            name="ck_users_status",
        ),
    )

    # Relationships
    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        foreign_keys="UserRole.user_id",
        back_populates="user",
        passive_deletes=True,
    )
    keys: Mapped[list["UserKey"]] = relationship(
        "UserKey",
        foreign_keys="UserKey.user_id",
        back_populates="user",
        passive_deletes=True,
    )


class UserRole(Base):
    """User Role Assignment (Composite Primary Key)."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(30), primary_key=True, nullable=False)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin', 'auditor')",
            name="ck_user_roles_role",
        ),
        Index("ix_user_roles_role_user_id", "role", "user_id"),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="roles",
    )
    assigner: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_by],
    )


class UserKey(Base, UUIDPrimaryKeyMixin):
    """User Public Cryptographic Keys (Encryption & Signing)."""

    __tablename__ = "user_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    key_purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(40), nullable=False)
    public_key_jwk: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    public_key_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "key_purpose IN ('encryption', 'signing')",
            name="ck_user_keys_key_purpose",
        ),
        CheckConstraint(
            "key_version > 0",
            name="ck_user_keys_key_version",
        ),
        CheckConstraint(
            "status IN ('active', 'retired', 'revoked')",
            name="ck_user_keys_status",
        ),
        UniqueConstraint(
            "user_id",
            "key_purpose",
            "key_version",
            name="uq_user_keys_user_purpose_version",
        ),
        Index("ix_user_keys_user_purpose_status", "user_id", "key_purpose", "status"),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="keys",
    )
