import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.security import verify_user_signature
from app.models.access import AccessGrant, AccessPolicy
from app.models.attribute import AttributeDefinition, UserAttribute
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.models.user import UserKey
from app.policies.evaluator import evaluate_policy
from app.schemas.document import (
    CreateDocumentRequest,
    CreateVersionRequest,
    DocumentResponse,
    DocumentUpdateRequest,
    DocumentVersionResponse,
    DownloadUrlResponse,
    FinalizeVersionRequest,
    PresignedUrlResponse,
)
from app.storage.adapter import get_storage_adapter


def _format_version_response(version: DocumentVersion) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        key_version=version.key_version,
        object_key=version.object_key,
        ciphertext_size_bytes=version.ciphertext_size_bytes,
        ciphertext_sha256_hex=version.ciphertext_sha256.hex(),
        manifest=version.manifest,
        status=version.status,
        signature_hex=version.signature.hex() if version.signature else None,
        signature_algorithm=version.signature_algorithm,
        created_at=version.created_at,
    )


def _format_document_response(doc: Document) -> DocumentResponse:
    current_ver = _format_version_response(doc.current_version) if doc.current_version else None
    return DocumentResponse(
        id=doc.id,
        owner_id=doc.owner_id,
        display_name=doc.display_name,
        media_type=doc.media_type,
        status=doc.status,
        current_version=current_ver,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def _check_caller_access(
    db: AsyncSession,
    document: Document,
    caller_id: uuid.UUID,
    required_permission: Optional[str] = None,
) -> bool:
    """Return True if caller is owner or has an active, valid grant with the required permission."""
    if document.owner_id == caller_id:
        return True

    now = datetime.now(timezone.utc)
    stmt = select(AccessGrant).where(
        AccessGrant.document_id == document.id,
        AccessGrant.grantee_user_id == caller_id,
        AccessGrant.status == "active",
        or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
    )
    grants = (await db.execute(stmt)).scalars().all()
    if not grants:
        return False

    if required_permission:
        for g in grants:
            if required_permission in g.permissions or "admin" in g.permissions:
                return True
        return False

    return True


async def create_document(
    db: AsyncSession,
    owner_id: uuid.UUID,
    payload: CreateDocumentRequest,
) -> DocumentResponse:
    """Create a new encrypted document root for the calling owner."""
    doc = Document(
        owner_id=owner_id,
        display_name=payload.display_name.strip(),
        media_type=payload.media_type.strip() if payload.media_type else None,
        status="active",
        current_version_id=None,
    )
    db.add(doc)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="document.created",
        outcome="success",
        actor_user_id=owner_id,
        document_id=doc.id,
        metadata={"display_name": doc.display_name, "media_type": doc.media_type},
    )

    return _format_document_response(doc)


async def create_version_intent(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: CreateVersionRequest,
) -> DocumentVersionResponse:
    """Create a draft version upload intent and allocate an object storage key."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()

    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    is_authorized = await _check_caller_access(db, doc, caller_id, required_permission="write")
    if not is_authorized:
        # IDOR protection: return 404 rather than leaking existence
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    # Determine next version number
    v_stmt = select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
        DocumentVersion.document_id == document_id
    )
    next_ver_num = (await db.execute(v_stmt)).scalar_one() + 1

    version_id = uuid.uuid4()
    object_key = f"blobs/{document_id}/{version_id}.enc"
    sha256_bytes = bytes.fromhex(payload.ciphertext_sha256_hex)

    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=next_ver_num,
        key_version=payload.key_version,
        object_key=object_key,
        ciphertext_size_bytes=payload.ciphertext_size_bytes,
        ciphertext_sha256=sha256_bytes,
        manifest=payload.manifest,
        commitment_version=payload.commitment_version,
        status="pending",
        created_by=caller_id,
    )
    db.add(version)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="document.version.created",
        outcome="success",
        actor_user_id=caller_id,
        document_id=document_id,
        metadata={
            "version_id": str(version.id),
            "version_number": version.version_number,
            "ciphertext_size_bytes": version.ciphertext_size_bytes,
        },
    )

    return _format_version_response(version)


async def issue_upload_url(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
) -> PresignedUrlResponse:
    """Generate a short-lived presigned PUT URL for direct client upload to Cloudflare R2 / MinIO."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    is_authorized = await _check_caller_access(db, doc, caller_id, required_permission="write")
    if not is_authorized:
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = (await db.execute(ver_stmt)).scalar_one_or_none()
    if not version:
        raise NotFoundException("Document version not found", code="VERSION_NOT_FOUND")

    if version.status != "pending":
        raise ValidationException(
            message=f"Upload URL can only be generated for pending versions (current: '{version.status}')",
            code="VERSION_NOT_PENDING",
        )

    storage = get_storage_adapter()
    expires_in = 300
    upload_url = storage.generate_presigned_upload_url(
        object_key=version.object_key,
        expires_in=expires_in,
    )

    return PresignedUrlResponse(
        url=upload_url,
        expires_in=expires_in,
        object_key=version.object_key,
    )


async def finalize_version(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: FinalizeVersionRequest,
) -> DocumentResponse:
    """Verify object existence in R2/MinIO, validate owner signature, store owner DEK envelope, and activate version."""
    doc_stmt = (
        select(Document)
        .options(selectinload(Document.current_version))
        .where(Document.id == document_id)
    )
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    is_authorized = await _check_caller_access(db, doc, caller_id, required_permission="write")
    if not is_authorized:
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = (await db.execute(ver_stmt)).scalar_one_or_none()
    if not version:
        raise NotFoundException("Document version not found", code="VERSION_NOT_FOUND")

    if version.status != "pending":
        raise ValidationException(
            message=f"Only pending versions can be finalized (current: '{version.status}')",
            code="VERSION_NOT_PENDING",
        )

    # 1. Storage Verification: Verify ciphertext actually exists in R2/MinIO
    storage = get_storage_adapter()
    exists, size_bytes, etag = storage.verify_object_exists(version.object_key)
    if not exists:
        raise ValidationException(
            message="Uploaded ciphertext object was not found in storage. Upload must be completed before finalization.",
            code="STORAGE_OBJECT_NOT_FOUND",
        )

    # 2. Owner Signature Verification (if provided)
    if payload.signature_hex or payload.signing_key_id:
        if not (payload.signature_hex and payload.signing_key_id):
            raise ValidationException(
                message="Both signature_hex and signing_key_id must be provided together",
                code="INCOMPLETE_SIGNATURE_DATA",
            )

        key_stmt = select(UserKey).where(
            UserKey.id == payload.signing_key_id,
            UserKey.user_id == caller_id,
            UserKey.key_purpose == "signing",
        )
        signing_key = (await db.execute(key_stmt)).scalar_one_or_none()
        if not signing_key or signing_key.status != "active":
            raise ValidationException(
                message="Registered signing key not found or inactive",
                code="INVALID_SIGNING_KEY",
            )

        try:
            sig_bytes = bytes.fromhex(payload.signature_hex)
        except ValueError:
            raise ValidationException("Invalid hexadecimal signature format", code="INVALID_SIGNATURE")

        is_valid = verify_user_signature(
            public_key_jwk=signing_key.public_key_jwk,
            signature_bytes=sig_bytes,
            data_bytes=version.ciphertext_sha256,
        )
        if not is_valid:
            raise ValidationException(
                message="Cryptographic signature verification failed against registered signing key",
                code="INVALID_SIGNATURE",
            )

        version.signature = sig_bytes
        version.signature_algorithm = payload.signature_algorithm or "ECDSA-P256"
        version.signing_key_id = payload.signing_key_id

    # 3. Create Owner's DocumentKeyEnvelope so owner can decrypt their own file
    enc_key_stmt = select(UserKey).where(
        UserKey.id == payload.recipient_encryption_key_id,
        UserKey.user_id == caller_id,
        UserKey.key_purpose == "encryption",
    )
    encryption_key = (await db.execute(enc_key_stmt)).scalar_one_or_none()
    if not encryption_key or encryption_key.status != "active":
        raise ValidationException(
            message="Recipient encryption key not found or inactive",
            code="INVALID_ENCRYPTION_KEY",
        )

    try:
        wrapped_key_bytes = base64.b64decode(payload.wrapped_dek)
    except Exception:
        raise ValidationException("Invalid base64 encoding for wrapped_dek", code="INVALID_WRAPPED_KEY")

    envelope = DocumentKeyEnvelope(
        document_version_id=version.id,
        recipient_user_id=caller_id,
        recipient_encryption_key_id=payload.recipient_encryption_key_id,
        wrapping_algorithm=encryption_key.algorithm or "RSA-OAEP-3072",
        wrapped_key=wrapped_key_bytes,
        envelope_version=1,
        status="active",
        created_by=caller_id,
    )
    db.add(envelope)

    # 3b. Optional recipient envelopes for multi-recipient re-keying on version rotation
    if payload.recipient_envelopes:
        for r_item in payload.recipient_envelopes:
            try:
                r_wrapped_key = base64.b64decode(r_item.wrapped_dek)
            except Exception:
                continue
            r_env = DocumentKeyEnvelope(
                document_version_id=version.id,
                recipient_user_id=r_item.recipient_user_id,
                recipient_encryption_key_id=r_item.recipient_encryption_key_id,
                wrapping_algorithm=r_item.wrapping_algorithm or "RSA-OAEP-3072",
                wrapped_key=r_wrapped_key,
                envelope_version=1,
                status="active",
                created_by=caller_id,
            )
            db.add(r_env)

    # 4. Activate version and update document root
    version.status = "finalized"
    doc.current_version_id = version.id
    doc.updated_at = datetime.now(timezone.utc)

    db.add(version)
    db.add(doc)
    await db.flush()

    # 5. Record Audit Events
    await record_audit_event(
        db=db,
        event_type="document.version.uploaded",
        outcome="success",
        actor_user_id=caller_id,
        document_id=doc.id,
        metadata={"version_id": str(version.id), "object_key": version.object_key},
    )
    await record_audit_event(
        db=db,
        event_type="document.version.finalized",
        outcome="success",
        actor_user_id=caller_id,
        document_id=doc.id,
        metadata={
            "version_id": str(version.id),
            "version_number": version.version_number,
            "has_signature": version.signature is not None,
        },
    )

    doc.current_version = version
    return _format_document_response(doc)


async def issue_download_url(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DownloadUrlResponse:
    """Authorize caller, generate presigned GET download URL, and return caller's wrapped DEK envelope."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    now = datetime.now(timezone.utc)

    # 1. Dual-layer authorization check when caller is not the owner
    if doc.owner_id != caller_id:
        grant_stmt = select(AccessGrant).where(
            AccessGrant.document_id == document_id,
            AccessGrant.grantee_user_id == caller_id,
        )
        grants = (await db.execute(grant_stmt)).scalars().all()
        if not grants:
            # IDOR defense: return 404
            raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

        active_grant = next(
            (
                g
                for g in grants
                if g.status == "active"
                and (g.expires_at is None or g.expires_at > now)
                and ("download" in g.permissions or "admin" in g.permissions)
            ),
            None,
        )
        if not active_grant:
            raise ForbiddenException(
                message="Access grant has been revoked, expired, or lacks download permission",
                code="ACCESS_REVOKED",
            )

        # Re-evaluate active ABAC policy against caller's live attributes
        pol_stmt = select(AccessPolicy).where(
            AccessPolicy.document_id == document_id,
            AccessPolicy.status == "active",
        )
        active_policy = (await db.execute(pol_stmt)).scalar_one_or_none()
        if active_policy:
            attrs_stmt = (
                select(UserAttribute, AttributeDefinition)
                .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
                .where(
                    UserAttribute.user_id == caller_id,
                    AttributeDefinition.is_active.is_(True),
                    UserAttribute.valid_from <= now,
                    or_(UserAttribute.valid_until.is_(None), UserAttribute.valid_until > now),
                )
            )
            attr_results = (await db.execute(attrs_stmt)).all()
            caller_attrs = {defn.name: ua.value for ua, defn in attr_results}
            if not evaluate_policy(active_policy.policy_ast, caller_attrs):
                raise ForbiddenException(
                    message="Recipient attributes do not satisfy active document ABAC policy",
                    code="ABAC_POLICY_DENIED",
                )

    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = (await db.execute(ver_stmt)).scalar_one_or_none()
    if not version or version.status != "finalized":
        raise NotFoundException("Finalized document version not found", code="VERSION_NOT_FOUND")

    # Fetch caller's active key envelope for this version
    env_stmt = select(DocumentKeyEnvelope).where(
        DocumentKeyEnvelope.document_version_id == version.id,
        DocumentKeyEnvelope.recipient_user_id == caller_id,
        DocumentKeyEnvelope.status == "active",
    )
    envelope = (await db.execute(env_stmt)).scalar_one_or_none()
    if not envelope:
        raise ForbiddenException(
            message="No active decryption key envelope found for caller on this document version",
            code="NO_KEY_ENVELOPE",
        )

    storage = get_storage_adapter()
    expires_in = 300
    download_url = storage.generate_presigned_download_url(
        object_key=version.object_key,
        expires_in=expires_in,
        response_content_disposition=f'attachment; filename="{doc.display_name}"',
    )

    await record_audit_event(
        db=db,
        event_type="document.version.downloaded",
        outcome="success",
        actor_user_id=caller_id,
        document_id=doc.id,
        metadata={"version_id": str(version.id), "version_number": version.version_number},
    )

    return DownloadUrlResponse(
        download_url=download_url,
        expires_in=expires_in,
        object_key=version.object_key,
        wrapped_dek=base64.b64encode(envelope.wrapped_key).decode("ascii"),
        wrapping_algorithm=envelope.wrapping_algorithm,
        recipient_encryption_key_id=envelope.recipient_encryption_key_id,
        manifest=version.manifest,
        ciphertext_size_bytes=version.ciphertext_size_bytes,
        ciphertext_sha256_hex=version.ciphertext_sha256.hex(),
    )


async def list_documents(
    db: AsyncSession,
    caller_id: uuid.UUID,
    filter_type: str = "all",
    page: int = 1,
    page_size: int = 50,
) -> List[DocumentResponse]:
    """List documents accessible to caller, supporting owned vs shared filters."""
    offset = max(0, (page - 1) * page_size)
    limit = min(max(1, page_size), 100)

    now = datetime.now(timezone.utc)
    active_grants_subq = (
        select(AccessGrant.document_id)
        .where(
            AccessGrant.grantee_user_id == caller_id,
            AccessGrant.status == "active",
            or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
        )
        .scalar_subquery()
    )

    stmt = (
        select(Document)
        .options(selectinload(Document.current_version))
        .where(Document.status != "deleted")
    )

    if filter_type == "owned":
        stmt = stmt.where(Document.owner_id == caller_id)
    elif filter_type == "shared":
        stmt = stmt.where(
            Document.owner_id != caller_id,
            Document.id.in_(active_grants_subq),
        )
    else:  # "all"
        stmt = stmt.where(
            or_(
                Document.owner_id == caller_id,
                Document.id.in_(active_grants_subq),
            )
        )

    stmt = stmt.order_by(Document.updated_at.desc()).offset(offset).limit(limit)
    docs = (await db.execute(stmt)).scalars().all()
    return [_format_document_response(d) for d in docs]


async def get_document(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
) -> DocumentResponse:
    """Retrieve document details and current version metadata."""
    stmt = (
        select(Document)
        .options(selectinload(Document.current_version))
        .where(Document.id == document_id)
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    is_authorized = await _check_caller_access(db, doc, caller_id)
    if not is_authorized:
        # IDOR protection
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    return _format_document_response(doc)


async def delete_document(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """Soft-delete an encrypted document. Only the document owner may perform deletion."""
    stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != caller_id:
        raise ForbiddenException(
            message="Only the document owner can delete this document",
            code="FORBIDDEN_DELETE",
        )

    doc.status = "deleted"
    doc.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="document.deleted",
        outcome="success",
        actor_user_id=caller_id,
        document_id=document_id,
        metadata={"display_name": doc.display_name},
    )


async def update_document(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentUpdateRequest,
) -> DocumentResponse:
    """Update document metadata (display_name, media_type). Owner only."""
    stmt = (
        select(Document)
        .options(selectinload(Document.current_version))
        .where(Document.id == document_id)
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != caller_id:
        raise ForbiddenException("Only the document owner can update metadata", code="FORBIDDEN")

    changed = False
    if payload.display_name is not None and payload.display_name.strip():
        doc.display_name = payload.display_name.strip()
        changed = True
    if payload.media_type is not None:
        doc.media_type = payload.media_type.strip() if payload.media_type else None
        changed = True

    if changed:
        doc.updated_at = datetime.now(timezone.utc)
        await db.flush()

        await record_audit_event(
            db=db,
            event_type="document.updated",
            outcome="success",
            actor_user_id=caller_id,
            document_id=document_id,
            metadata={"display_name": doc.display_name, "media_type": doc.media_type},
        )

    return _format_document_response(doc)


async def list_document_versions(
    db: AsyncSession,
    caller_id: uuid.UUID,
    document_id: uuid.UUID,
) -> List[DocumentVersionResponse]:
    """List all finalized versions of a document for an authorized viewer."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    is_authorized = await _check_caller_access(db, doc, caller_id, required_permission="read")
    if not is_authorized:
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    stmt = (
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == "finalized",
        )
        .order_by(DocumentVersion.version_number.desc())
    )
    versions = (await db.execute(stmt)).scalars().all()
    return [_format_version_response(v) for v in versions]
