import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    BigInteger,
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


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Core Document Metadata Model."""

    __tablename__ = "documents"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            name="fk_documents_current_version_id",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'deleted', 'quarantined')",
            name="ck_documents_status",
        ),
        Index("ix_documents_owner_status_updated", "owner_id", "status", "updated_at"),
        Index("ix_documents_owner_created", "owner_id", "created_at"),
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])  # noqa: F821
    current_version: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        foreign_keys="DocumentVersion.document_id",
        back_populates="document",
        passive_deletes=True,
    )


class DocumentVersion(Base, UUIDPrimaryKeyMixin):
    """Specific Immutable Version of an Encrypted Document."""

    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    ciphertext_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ciphertext_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    manifest: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    signature: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    signature_algorithm: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    signing_key_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_keys.id", ondelete="RESTRICT"),
        nullable=True,
    )
    commitment_version: Mapped[str] = mapped_column(String(30), nullable=False, default="v1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "version_number > 0",
            name="ck_document_versions_version_number",
        ),
        CheckConstraint(
            "key_version > 0",
            name="ck_document_versions_key_version",
        ),
        CheckConstraint(
            "ciphertext_size_bytes >= 0",
            name="ck_document_versions_ciphertext_size",
        ),
        CheckConstraint(
            "status IN ('pending', 'finalized', 'retired', 'failed')",
            name="ck_document_versions_status",
        ),
        CheckConstraint(
            "(signature IS NULL AND signature_algorithm IS NULL) OR "
            "(signature IS NOT NULL AND signature_algorithm IS NOT NULL)",
            name="ck_document_versions_signature_parity",
        ),
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_doc_version",
        ),
        Index("ix_document_versions_doc_version", "document_id", "version_number"),
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[document_id],
        back_populates="versions",
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    signing_key: Mapped[Optional["UserKey"]] = relationship(  # noqa: F821
        "UserKey",
        foreign_keys=[signing_key_id],
    )
    key_envelopes: Mapped[list["DocumentKeyEnvelope"]] = relationship(
        "DocumentKeyEnvelope",
        back_populates="document_version",
        passive_deletes=True,
    )


class DocumentKeyEnvelope(Base, UUIDPrimaryKeyMixin):
    """Wrapped Data Encryption Key (DEK) for Authorized Recipients."""

    __tablename__ = "document_key_envelopes"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recipient_encryption_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_keys.id", ondelete="RESTRICT"),
        nullable=False,
    )
    wrapping_algorithm: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="RSA-OAEP-3072",
    )
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    envelope_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "envelope_version > 0",
            name="ck_doc_key_envelopes_version",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked', 'superseded')",
            name="ck_doc_key_envelopes_status",
        ),
        UniqueConstraint(
            "document_version_id",
            "recipient_user_id",
            "recipient_encryption_key_id",
            "envelope_version",
            name="uq_doc_key_envelopes_unique_recipient_env",
        ),
        Index(
            "ix_doc_key_envelopes_recipient_status_created",
            "recipient_user_id",
            "status",
            "created_at",
        ),
        Index("ix_doc_key_envelopes_version_status", "document_version_id", "status"),
    )

    # Relationships
    document_version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion",
        foreign_keys=[document_version_id],
        back_populates="key_envelopes",
    )
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_user_id])  # noqa: F821
    recipient_key: Mapped["UserKey"] = relationship(  # noqa: F821
        "UserKey",
        foreign_keys=[recipient_encryption_key_id],
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
