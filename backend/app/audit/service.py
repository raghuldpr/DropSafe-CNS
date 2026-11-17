import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.merkle import (
    build_merkle_tree,
    compute_leaf_hash,
    generate_merkle_proof,
    verify_merkle_proof,
)
from app.core.config import settings
from app.core.exceptions import NotFoundException, ValidationException
from app.core.logging import get_logger, get_request_id
from app.models.access import AccessGrant
from app.models.audit import AuditBatch, AuditEvent, BlockchainAnchor, OutboxJob
from app.models.document import Document
from app.models.user import User
from app.schemas.audit import (
    AuditBatchResponse,
    AuditEventResponse,
    BlockchainAnchorResponse,
    MerkleProofResponse,
    VerifyChainResponse,
    VerifyProofRequest,
    VerifyProofResponse,
)

logger = get_logger(__name__)

# Sensitive keys that must be stripped from audit metadata payloads
FORBIDDEN_METADATA_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "wrapped_key",
    "private_key",
    "secret",
    "secret_key",
    "authorization",
    "cookie",
}


def sanitize_audit_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recursively sanitize metadata dictionary by removing sensitive credentials."""
    if not metadata:
        return {}

    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        key_lower = str(key).lower()
        if any(forbidden in key_lower for forbidden in FORBIDDEN_METADATA_KEYS):
            continue

        if isinstance(value, dict):
            sanitized[key] = sanitize_audit_metadata(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_audit_metadata(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, uuid.UUID):
            sanitized[key] = str(value)
        elif isinstance(value, bytes):
            sanitized[key] = value.hex()
        elif isinstance(value, datetime):
            sanitized[key] = value.isoformat()
        else:
            sanitized[key] = value

    return sanitized


def compute_audit_event_hash(
    sequence_number: int,
    event_type: str,
    outcome: str,
    actor_user_id: Optional[uuid.UUID],
    document_id: Optional[uuid.UUID],
    occurred_at_iso: str,
    metadata: Dict[str, Any],
    previous_event_hash: Optional[bytes],
) -> bytes:
    """Compute deterministic SHA-256 digest over canonical JSON representation of event attributes."""
    canonical_payload = {
        "sequence_number": sequence_number,
        "event_type": event_type,
        "outcome": outcome,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "document_id": str(document_id) if document_id else None,
        "occurred_at": occurred_at_iso,
        "metadata": metadata,
        "previous_event_hash": previous_event_hash.hex() if previous_event_hash else None,
    }
    canonical_bytes = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).digest()


async def record_audit_event(
    db: AsyncSession,
    event_type: str,
    outcome: str,
    actor_user_id: Optional[uuid.UUID] = None,
    document_id: Optional[uuid.UUID] = None,
    request_id: Optional[str] = None,
    source_ip_hash: Optional[bytes] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Append a cryptographically hash-chained audit event to the append-only ledger."""
    # 1. Resolve context parameters
    req_id = request_id or get_request_id() or None
    occurred_at = datetime.now(timezone.utc)
    occurred_at_iso = occurred_at.isoformat()
    clean_metadata = sanitize_audit_metadata(metadata)

    # 2. Determine next sequence number and retrieve previous event hash
    seq_stmt = select(func.coalesce(func.max(AuditEvent.sequence_number), 0))
    current_max_seq = (await db.execute(seq_stmt)).scalar_one()
    next_seq = current_max_seq + 1

    prev_hash_stmt = (
        select(AuditEvent.event_hash)
        .order_by(AuditEvent.sequence_number.desc())
        .limit(1)
    )
    previous_event_hash = (await db.execute(prev_hash_stmt)).scalar_one_or_none()

    # 3. Compute deterministic event hash
    event_hash = compute_audit_event_hash(
        sequence_number=next_seq,
        event_type=event_type,
        outcome=outcome,
        actor_user_id=actor_user_id,
        document_id=document_id,
        occurred_at_iso=occurred_at_iso,
        metadata=clean_metadata,
        previous_event_hash=previous_event_hash,
    )

    # 4. Create and persist AuditEvent
    event = AuditEvent(
        sequence_number=next_seq,
        actor_user_id=actor_user_id,
        document_id=document_id,
        event_type=event_type,
        outcome=outcome,
        occurred_at=occurred_at,
        request_id=req_id,
        source_ip_hash=source_ip_hash,
        metadata_payload=clean_metadata,
        previous_event_hash=previous_event_hash,
        event_hash=event_hash,
    )
    db.add(event)
    await db.flush()

    logger.info(
        f"Audit event recorded: seq={next_seq} type='{event_type}' outcome='{outcome}' actor={actor_user_id}"
    )
    return event


def _format_event_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        sequence_number=event.sequence_number,
        event_type=event.event_type,
        outcome=event.outcome,
        actor_user_id=event.actor_user_id,
        document_id=event.document_id,
        occurred_at=event.occurred_at,
        event_hash_hex=event.event_hash.hex(),
        previous_event_hash_hex=event.previous_event_hash.hex() if event.previous_event_hash else None,
        batch_id=event.batch_id,
        metadata_payload=event.metadata_payload,
    )


def _format_batch_response(
    batch: AuditBatch,
    anchors: Optional[List[BlockchainAnchor]] = None,
) -> AuditBatchResponse:
    anchors_list = []
    if anchors is not None:
        raw_anchors = anchors
    elif "anchors" in batch.__dict__ and batch.__dict__["anchors"]:
        raw_anchors = batch.__dict__["anchors"]
    else:
        raw_anchors = []

    for a in raw_anchors:
        anchors_list.append({
            "id": str(a.id),
            "chain_id": a.chain_id,
            "network_name": a.network_name,
            "contract_address": a.contract_address,
            "transaction_hash": a.transaction_hash,
            "block_number": a.block_number,
            "status": a.status,
            "confirmed_at": a.confirmed_at.isoformat() if a.confirmed_at else None,
        })

    return AuditBatchResponse(
        id=batch.id,
        batch_number=batch.batch_number,
        first_sequence_number=batch.first_sequence_number,
        last_sequence_number=batch.last_sequence_number,
        event_count=batch.event_count,
        merkle_root_hex=batch.merkle_root.hex(),
        status=batch.status,
        created_at=batch.created_at,
        anchored_at=batch.anchored_at,
        anchors=anchors_list,
    )


async def get_audit_events(
    db: AsyncSession,
    caller: User,
    page: int = 1,
    page_size: int = 50,
    document_id: Optional[uuid.UUID] = None,
) -> List[AuditEventResponse]:
    """Retrieve audit events based on caller role and document ownership/grants."""
    caller_roles = [r.role for r in caller.roles]
    is_admin_or_auditor = any(r in ("admin", "auditor") for r in caller_roles)

    offset = max(0, (page - 1) * page_size)
    limit = min(max(1, page_size), 100)

    stmt = select(AuditEvent).order_by(AuditEvent.sequence_number.desc())

    if is_admin_or_auditor:
        if document_id:
            stmt = stmt.where(AuditEvent.document_id == document_id)
    else:
        # Regular user: can see events where they were the actor,
        # or events for documents they own or have active grants on
        now = datetime.now(timezone.utc)
        owned_subq = select(Document.id).where(Document.owner_id == caller.id).scalar_subquery()
        granted_subq = (
            select(AccessGrant.document_id)
            .where(
                AccessGrant.grantee_user_id == caller.id,
                AccessGrant.status == "active",
                or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
            )
            .scalar_subquery()
        )

        filter_condition = or_(
            AuditEvent.actor_user_id == caller.id,
            AuditEvent.document_id.in_(owned_subq),
            AuditEvent.document_id.in_(granted_subq),
        )
        if document_id:
            stmt = stmt.where(filter_condition, AuditEvent.document_id == document_id)
        else:
            stmt = stmt.where(filter_condition)

    stmt = stmt.offset(offset).limit(limit)
    events = (await db.execute(stmt)).scalars().all()
    return [_format_event_response(e) for e in events]


async def get_event_by_id(
    db: AsyncSession,
    caller: User,
    event_id: uuid.UUID,
) -> AuditEventResponse:
    """Retrieve single audit event with caller visibility checks."""
    stmt = select(AuditEvent).where(AuditEvent.id == event_id)
    event = (await db.execute(stmt)).scalar_one_or_none()
    if not event:
        raise NotFoundException("Audit event not found", code="EVENT_NOT_FOUND")

    caller_roles = [r.role for r in caller.roles]
    is_privileged = any(r in ("admin", "auditor") for r in caller_roles)

    if not is_privileged:
        now = datetime.now(timezone.utc)
        is_actor = event.actor_user_id == caller.id
        is_doc_owner = False
        is_grantee = False

        if event.document_id:
            doc = (await db.execute(select(Document).where(Document.id == event.document_id))).scalar_one_or_none()
            if doc and doc.owner_id == caller.id:
                is_doc_owner = True

            grant = (
                await db.execute(
                    select(AccessGrant).where(
                        AccessGrant.document_id == event.document_id,
                        AccessGrant.grantee_user_id == caller.id,
                        AccessGrant.status == "active",
                        or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
                    )
                )
            ).scalar_one_or_none()
            if grant:
                is_grantee = True

        if not (is_actor or is_doc_owner or is_grantee):
            raise NotFoundException("Audit event not found", code="EVENT_NOT_FOUND")

    return _format_event_response(event)


async def create_audit_batch(
    db: AsyncSession,
    max_events: Optional[int] = None,
) -> Optional[AuditBatchResponse]:
    """Aggregate unbatched audit events into a deterministic Merkle tree and enqueue anchoring job."""
    batch_size = max_events or settings.AUDIT_BATCH_SIZE

    # Select unbatched events ordered by sequence_number
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.batch_id.is_(None))
        .order_by(AuditEvent.sequence_number.asc())
        .limit(batch_size)
    )
    events = (await db.execute(stmt)).scalars().all()
    if not events:
        return None

    # Compute leaves with domain separation prefix (0x00 || event_hash)
    leaf_hashes = [compute_leaf_hash(e.event_hash) for e in events]
    merkle_root, _ = build_merkle_tree(leaf_hashes)

    b_num_stmt = select(func.coalesce(func.max(AuditBatch.batch_number), 0))
    next_batch_num = (await db.execute(b_num_stmt)).scalar_one() + 1

    batch = AuditBatch(
        batch_number=next_batch_num,
        first_sequence_number=events[0].sequence_number,
        last_sequence_number=events[-1].sequence_number,
        event_count=len(events),
        merkle_root=merkle_root,
        tree_algorithm="SHA-256-MERKLE-v1",
        status="prepared",
    )
    db.add(batch)
    await db.flush()

    # Link events to the batch
    event_ids = [e.id for e in events]
    await db.execute(
        update(AuditEvent)
        .where(AuditEvent.id.in_(event_ids))
        .values(batch_id=batch.id)
    )

    # Enqueue Outbox job for asynchronous anchoring
    outbox_job = OutboxJob(
        job_type="anchor_batch",
        aggregate_id=batch.id,
        status="pending",
        attempt_count=0,
        run_after=datetime.now(timezone.utc),
    )
    db.add(outbox_job)
    await db.flush()

    logger.info(
        f"Audit batch created: batch_number={batch.batch_number} events={batch.event_count} root={batch.merkle_root.hex()}"
    )
    return _format_batch_response(batch, anchors=[])


async def get_audit_batch(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> AuditBatchResponse:
    """Retrieve audit batch details including associated anchors."""
    stmt = (
        select(AuditBatch)
        .options(selectinload(AuditBatch.anchors))
        .where(AuditBatch.id == batch_id)
    )
    batch = (await db.execute(stmt)).scalar_one_or_none()
    if not batch:
        raise NotFoundException("Audit batch not found", code="BATCH_NOT_FOUND")

    return _format_batch_response(batch)


async def get_event_proof(
    db: AsyncSession,
    batch_id: uuid.UUID,
    event_id: uuid.UUID,
) -> MerkleProofResponse:
    """Generate Merkle inclusion proof for an event within a specific batch."""
    b_stmt = select(AuditBatch).where(AuditBatch.id == batch_id)
    batch = (await db.execute(b_stmt)).scalar_one_or_none()
    if not batch:
        raise NotFoundException("Audit batch not found", code="BATCH_NOT_FOUND")

    events_stmt = (
        select(AuditEvent)
        .where(AuditEvent.batch_id == batch_id)
        .order_by(AuditEvent.sequence_number.asc())
    )
    events = (await db.execute(events_stmt)).scalars().all()

    target_idx: Optional[int] = None
    target_event: Optional[AuditEvent] = None
    for idx, e in enumerate(events):
        if e.id == event_id:
            target_idx = idx
            target_event = e
            break

    if target_idx is None or target_event is None:
        raise NotFoundException(
            message=f"Event '{event_id}' is not in batch '{batch_id}'",
            code="EVENT_NOT_IN_BATCH",
        )

    leaf_hashes = [compute_leaf_hash(e.event_hash) for e in events]
    root_hash, tree_levels = build_merkle_tree(leaf_hashes)

    proof = generate_merkle_proof(target_idx, tree_levels)
    target_leaf_hash = leaf_hashes[target_idx]

    return MerkleProofResponse(
        batch_id=batch.id,
        event_id=target_event.id,
        event_sequence_number=target_event.sequence_number,
        leaf_hash_hex=target_leaf_hash.hex(),
        merkle_root_hex=root_hash.hex(),
        proof=proof,
    )


async def verify_proof(
    db: AsyncSession,
    payload: VerifyProofRequest,
) -> VerifyProofResponse:
    """Cryptographically verify a Merkle audit inclusion proof and correlate with ledger batches."""
    try:
        leaf_hash = bytes.fromhex(payload.leaf_hash_hex)
        expected_root = bytes.fromhex(payload.merkle_root_hex)
    except ValueError:
        raise ValidationException("Invalid hex encoding for leaf_hash or merkle_root")

    is_valid = verify_merkle_proof(leaf_hash, payload.proof, expected_root)
    if not is_valid:
        return VerifyProofResponse(is_valid=False, matched_batch_id=None, anchor_status=None)

    # Check if expected_root matches a stored AuditBatch
    b_stmt = select(AuditBatch).where(AuditBatch.merkle_root == expected_root)
    matched_batch = (await db.execute(b_stmt)).scalar_one_or_none()

    if matched_batch:
        return VerifyProofResponse(
            is_valid=True,
            matched_batch_id=matched_batch.id,
            anchor_status=matched_batch.status,
        )

    return VerifyProofResponse(is_valid=True, matched_batch_id=None, anchor_status=None)


async def list_audit_batches(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> List[AuditBatchResponse]:
    """Retrieve paginated list of audit batches with their blockchain anchor records."""
    offset = (page - 1) * page_size
    stmt = (
        select(AuditBatch)
        .options(selectinload(AuditBatch.anchors))
        .order_by(AuditBatch.batch_number.desc())
        .offset(offset)
        .limit(page_size)
    )
    batches = (await db.execute(stmt)).scalars().all()
    return [_format_batch_response(b) for b in batches]


async def get_batch_anchors(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> List[BlockchainAnchorResponse]:
    """Retrieve all blockchain anchor confirmation records for a specific audit batch."""
    b_stmt = select(AuditBatch).where(AuditBatch.id == batch_id)
    batch = (await db.execute(b_stmt)).scalar_one_or_none()
    if not batch:
        raise NotFoundException("Audit batch not found", code="BATCH_NOT_FOUND")

    stmt = (
        select(BlockchainAnchor)
        .where(BlockchainAnchor.batch_id == batch_id)
        .order_by(BlockchainAnchor.created_at.desc())
    )
    anchors = (await db.execute(stmt)).scalars().all()
    return [BlockchainAnchorResponse.model_validate(a) for a in anchors]


async def verify_event_hash_chain(db: AsyncSession) -> VerifyChainResponse:
    """Verify sequential previous_event_hash -> event_hash chain integrity across recorded audit events."""
    stmt = select(AuditEvent).order_by(AuditEvent.sequence_number.asc())
    events = (await db.execute(stmt)).scalars().all()
    if not events:
        return VerifyChainResponse(chain_valid=True, checked_events=0, first_broken_sequence=None)

    expected_prev_hash: Optional[bytes] = None
    for event in events:
        # 1. Verify previous_event_hash pointer
        if event.previous_event_hash != expected_prev_hash:
            logger.warning(
                f"Hash chain pointer mismatch at seq {event.sequence_number}: expected {expected_prev_hash.hex() if expected_prev_hash else None}, got {event.previous_event_hash.hex() if event.previous_event_hash else None}"
            )
            return VerifyChainResponse(
                chain_valid=False,
                checked_events=event.sequence_number - 1,
                first_broken_sequence=event.sequence_number,
            )

        # 2. Recompute canonical digest
        occurred_at_iso = (
            event.occurred_at.replace(tzinfo=timezone.utc).isoformat()
            if event.occurred_at.tzinfo is None
            else event.occurred_at.isoformat()
        )
        recomputed_hash = compute_audit_event_hash(
            sequence_number=event.sequence_number,
            event_type=event.event_type,
            outcome=event.outcome,
            actor_user_id=event.actor_user_id,
            document_id=event.document_id,
            occurred_at_iso=occurred_at_iso,
            metadata=event.metadata_payload,
            previous_event_hash=event.previous_event_hash,
        )
        if event.event_hash != recomputed_hash:
            logger.warning(
                f"Hash mismatch at seq {event.sequence_number}: expected {event.event_hash.hex()}, computed {recomputed_hash.hex()}.\n"
                f"occurred_at_iso={occurred_at_iso}\n"
                f"metadata={event.metadata_payload}"
            )
            return VerifyChainResponse(
                chain_valid=False,
                checked_events=event.sequence_number - 1,
                first_broken_sequence=event.sequence_number,
            )

        expected_prev_hash = event.event_hash

    return VerifyChainResponse(
        chain_valid=True,
        checked_events=len(events),
        first_broken_sequence=None,
    )
