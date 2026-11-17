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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin


class AuditBatch(Base, UUIDPrimaryKeyMixin):
    """Merkle Tree Aggregation Batch over a sequence of Audit Events."""

    __tablename__ = "audit_batches"

    batch_number: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    first_sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    merkle_root: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tree_algorithm: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="SHA-256-MERKLE-v1",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="prepared")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    anchored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "batch_number > 0",
            name="ck_audit_batches_batch_number",
        ),
        CheckConstraint(
            "event_count > 0",
            name="ck_audit_batches_event_count",
        ),
        CheckConstraint(
            "status IN ('prepared', 'anchoring', 'anchored', 'failed', 'superseded')",
            name="ck_audit_batches_status",
        ),
        CheckConstraint(
            "last_sequence_number >= first_sequence_number",
            name="ck_audit_batches_sequence_order",
        ),
        Index("ix_audit_batches_status_created", "status", "created_at"),
        Index("ix_audit_batches_first_last_seq", "first_sequence_number", "last_sequence_number"),
    )

    # Relationships
    events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="batch",
        passive_deletes=True,
    )
    anchors: Mapped[list["BlockchainAnchor"]] = relationship(
        "BlockchainAnchor",
        back_populates="batch",
        passive_deletes=True,
    )


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """Append-only, SHA-256 Hash Chained Security Event Log."""

    __tablename__ = "audit_events"

    sequence_number: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_ip_hash: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONBType,
        nullable=False,
        default=dict,
    )
    previous_event_hash: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    event_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_batches.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'denied', 'failure', 'pending')",
            name="ck_audit_events_outcome",
        ),
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_actor_occurred", "actor_user_id", "occurred_at"),
        Index("ix_audit_events_doc_occurred", "document_id", "occurred_at"),
        Index("ix_audit_events_type_occurred", "event_type", "occurred_at"),
    )

    # Relationships
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_user_id])  # noqa: F821
    document: Mapped[Optional["Document"]] = relationship(  # noqa: F821
        "Document", foreign_keys=[document_id]
    )
    batch: Mapped[Optional["AuditBatch"]] = relationship(
        "AuditBatch", foreign_keys=[batch_id], back_populates="events"
    )


class BlockchainAnchor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Distributed Ledger Anchor Transaction for an Audit Batch Merkle Root."""

    __tablename__ = "blockchain_anchors"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    network_name: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_address: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_hash: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    block_number: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'submitted', 'confirmed', 'failed', 'reorged')",
            name="ck_blockchain_anchors_status",
        ),
        CheckConstraint(
            "confirmation_count >= 0",
            name="ck_blockchain_anchors_confirmation_count",
        ),
        Index("ix_blockchain_anchors_status_created", "status", "created_at"),
        Index("ix_blockchain_anchors_batch_created", "batch_id", "created_at"),
    )

    # Relationships
    batch: Mapped["AuditBatch"] = relationship(
        "AuditBatch", foreign_keys=[batch_id], back_populates="anchors"
    )


class OutboxJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Reliable Asynchronous Outbox Worker Queue."""

    __tablename__ = "outbox_jobs"

    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('build_audit_batch', 'anchor_batch')",
            name="ck_outbox_jobs_job_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed', 'dead_letter')",
            name="ck_outbox_jobs_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_outbox_jobs_attempt_count",
        ),
        Index("ix_outbox_jobs_status_run_after", "status", "run_after"),
        Index("ix_outbox_jobs_type_aggregate", "job_type", "aggregate_id"),
        Index("ix_outbox_jobs_locked_at", "locked_at"),
    )
