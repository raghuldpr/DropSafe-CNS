import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, UUIDPrimaryKeyMixin


class AccessPolicy(Base, UUIDPrimaryKeyMixin):
    """ABAC Policy Rules Attached to a Document."""

    __tablename__ = "access_policies"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_schema_version: Mapped[str] = mapped_column(String(30), nullable=False, default="v1")
    policy_ast: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
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
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "version_number > 0",
            name="ck_access_policies_version_number",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'disabled')",
            name="ck_access_policies_status",
        ),
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_access_policies_doc_version",
        ),
        Index("ix_access_policies_doc_status_version", "document_id", "status", "version_number"),
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])  # noqa: F821
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821


class AccessGrant(Base, UUIDPrimaryKeyMixin):
    """Explicit or Link-Based Authorization Grant to a Document."""

    __tablename__ = "access_grants"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grantor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grantee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    grant_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    permissions: Mapped[List[str]] = mapped_column(JSONBType, nullable=False)
    policy_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("access_policies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "grant_type IN ('user', 'link')",
            name="ck_access_grants_grant_type",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_access_grants_status",
        ),
        CheckConstraint(
            "(grant_type = 'user' AND grantee_user_id IS NOT NULL) OR "
            "(grant_type = 'link' AND grantee_user_id IS NULL)",
            name="ck_access_grants_grantee_parity",
        ),
        Index("ix_access_grants_doc_status", "document_id", "status"),
        Index(
            "ix_access_grants_grantee_status_created",
            "grantee_user_id",
            "status",
            "created_at",
        ),
        Index("ix_access_grants_expires_at", "expires_at"),
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])  # noqa: F821
    grantor: Mapped["User"] = relationship("User", foreign_keys=[grantor_user_id])  # noqa: F821
    grantee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[grantee_user_id])  # noqa: F821
    policy: Mapped[Optional["AccessPolicy"]] = relationship(
        "AccessPolicy", foreign_keys=[policy_version_id]
    )
    share_links: Mapped[list["ShareLink"]] = relationship(
        "ShareLink",
        back_populates="access_grant",
        passive_deletes=True,
    )


class ShareLink(Base, UUIDPrimaryKeyMixin):
    """Anonymous Bearer Share Link Root (stores hash of token, never raw token)."""

    __tablename__ = "share_links"

    access_grant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("access_grants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    token_key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrapped_dek: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_share_links_status",
        ),
        CheckConstraint(
            "max_uses IS NULL OR max_uses > 0",
            name="ck_share_links_max_uses",
        ),
        CheckConstraint(
            "use_count >= 0",
            name="ck_share_links_use_count",
        ),
        Index("ix_share_links_status_expires", "status", "expires_at"),
    )

    # Relationships
    access_grant: Mapped["AccessGrant"] = relationship(
        "AccessGrant",
        foreign_keys=[access_grant_id],
        back_populates="share_links",
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
