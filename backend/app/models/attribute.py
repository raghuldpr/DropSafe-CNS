import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin


class AttributeDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """ABAC Attribute Definition Catalog."""

    __tablename__ = "attribute_definitions"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    allowed_values: Mapped[Optional[Any]] = mapped_column(JSONBType, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'boolean', 'integer', 'string_set')",
            name="ck_attribute_definitions_value_type",
        ),
        Index("ix_attribute_definitions_is_active_name", "is_active", "name"),
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    user_attributes: Mapped[list["UserAttribute"]] = relationship(
        "UserAttribute",
        back_populates="definition",
        passive_deletes=True,
    )


class UserAttribute(Base, UUIDPrimaryKeyMixin):
    """User Attribute Assignment for ABAC Evaluation."""

    __tablename__ = "user_attributes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    value: Mapped[Any] = mapped_column(JSONBType, nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="admin")
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_user_attributes_validity_window",
        ),
        UniqueConstraint(
            "user_id",
            "attribute_definition_id",
            name="uq_user_attributes_user_attr_def",
        ),
        Index("ix_user_attributes_user_attr_def", "user_id", "attribute_definition_id"),
        Index("ix_user_attributes_attr_valid_until", "attribute_definition_id", "valid_until"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # noqa: F821
    definition: Mapped["AttributeDefinition"] = relationship(
        "AttributeDefinition",
        foreign_keys=[attribute_definition_id],
        back_populates="user_attributes",
    )
    assigner: Mapped["User"] = relationship("User", foreign_keys=[assigned_by])  # noqa: F821


class AttributeCredentialSignature(Base, UUIDPrimaryKeyMixin):
    """Cryptographically Signed Attribute Credentials (Issuer-anchored)."""

    __tablename__ = "attribute_credential_signatures"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    credential_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    payload_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    issuer_key_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "credential_version > 0",
            name="ck_attr_cred_sigs_version",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded', 'revoked')",
            name="ck_attr_cred_sigs_status",
        ),
        UniqueConstraint(
            "user_id",
            "credential_version",
            name="uq_attr_cred_sigs_user_version",
        ),
        Index("ix_attr_cred_sigs_user_status_version", "user_id", "status", "credential_version"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # noqa: F821
