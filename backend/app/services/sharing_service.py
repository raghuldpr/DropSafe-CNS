import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.core.config import settings
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.access import AccessGrant, AccessPolicy, ShareLink
from app.models.attribute import AttributeDefinition, UserAttribute
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.models.user import User, UserKey
from app.policies.evaluator import evaluate_policy
from app.policies.validator import validate_policy_ast
from app.schemas.document import DocumentResponse
from app.schemas.sharing import (
    AccessGrantResponse,
    CreateGrantRequest,
    CreateShareLinkRequest,
    DocumentAccessOverviewResponse,
    EvaluateAccessResponse,
    PolicyResponse,
    PolicyUpdateRequest,
    RedeemShareLinkResponse,
    ShareLinkCreatedResponse,
    ShareLinkResponse,
    SharedDocumentResponse,
)
from app.services.document_service import _format_document_response
from app.storage.adapter import get_storage_adapter


def _format_policy_response(policy: Optional[AccessPolicy]) -> Optional[PolicyResponse]:
    if not policy:
        return None
    return PolicyResponse(
        id=policy.id,
        document_id=policy.document_id,
        version_number=policy.version_number,
        policy_schema_version=policy.policy_schema_version,
        policy_ast=policy.policy_ast,
        status=policy.status,
        created_at=policy.created_at,
        activated_at=policy.activated_at,
    )


def _format_grant_response(grant: AccessGrant) -> AccessGrantResponse:
    grantee_email = grant.grantee.email if grant.grantee else None
    grantee_display_name = grant.grantee.display_name if grant.grantee else None
    return AccessGrantResponse(
        id=grant.id,
        document_id=grant.document_id,
        grantor_user_id=grant.grantor_user_id,
        grantee_user_id=grant.grantee_user_id,
        grantee_email=grantee_email,
        grantee_display_name=grantee_display_name,
        grant_type=grant.grant_type,
        permissions=grant.permissions,
        status=grant.status,
        expires_at=grant.expires_at,
        created_at=grant.created_at,
        revoked_at=grant.revoked_at,
    )


async def get_user_effective_attributes(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Dict[str, Any]:
    """Retrieve all active, currently valid attributes assigned to a user."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserAttribute, AttributeDefinition)
        .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
        .where(
            UserAttribute.user_id == user_id,
            AttributeDefinition.is_active.is_(True),
            UserAttribute.valid_from <= now,
            or_(UserAttribute.valid_until.is_(None), UserAttribute.valid_until > now),
        )
    )
    results = (await db.execute(stmt)).all()
    attributes_dict: Dict[str, Any] = {}
    for ua, defn in results:
        attributes_dict[defn.name] = ua.value
    return attributes_dict


async def set_document_policy(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    payload: PolicyUpdateRequest,
) -> PolicyResponse:
    """Attach or update an ABAC policy on a document, validating AST and superseding previous versions."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException(
            message="Only the document owner can configure access policies",
            code="FORBIDDEN_POLICY_MANAGEMENT",
        )

    # 1. Validate AST syntax, limits, and operators
    validate_policy_ast(payload.policy_ast)

    # 2. Supersede prior active policy version
    await db.execute(
        update(AccessPolicy)
        .where(AccessPolicy.document_id == document_id, AccessPolicy.status == "active")
        .values(status="superseded")
    )

    # 3. Calculate next policy version number
    v_stmt = select(func.coalesce(func.max(AccessPolicy.version_number), 0)).where(
        AccessPolicy.document_id == document_id
    )
    next_ver = (await db.execute(v_stmt)).scalar_one() + 1

    now = datetime.now(timezone.utc)
    policy = AccessPolicy(
        document_id=document_id,
        version_number=next_ver,
        policy_schema_version=payload.policy_schema_version,
        policy_ast=payload.policy_ast,
        status="active",
        created_by=owner_user_id,
        activated_at=now,
    )
    db.add(policy)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="document.policy.updated",
        outcome="success",
        actor_user_id=owner_user_id,
        document_id=document_id,
        metadata={"version_number": policy.version_number},
    )

    return _format_policy_response(policy)  # type: ignore


async def get_document_policy(
    db: AsyncSession,
    document_id: uuid.UUID,
    caller_id: uuid.UUID,
) -> Optional[PolicyResponse]:
    """Retrieve active ABAC policy attached to a document."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    stmt = select(AccessPolicy).where(
        AccessPolicy.document_id == document_id,
        AccessPolicy.status == "active",
    )
    policy = (await db.execute(stmt)).scalar_one_or_none()
    return _format_policy_response(policy)


async def create_grant(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    payload: CreateGrantRequest,
) -> AccessGrantResponse:
    """Create a recipient access grant, evaluate ABAC eligibility, and store the recipient's wrapped DEK envelope."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException("Only the document owner can share this document", code="FORBIDDEN")

    if not doc.current_version_id:
        raise ValidationException(
            message="Cannot share a document without a finalized version",
            code="NO_FINALIZED_VERSION",
        )

    # 1. Recipient existence check
    recip_stmt = select(User).where(User.id == payload.grantee_user_id)
    recipient = (await db.execute(recip_stmt)).scalar_one_or_none()
    if not recipient or recipient.status != "active":
        raise NotFoundException("Recipient user not found or inactive", code="RECIPIENT_NOT_FOUND")

    # 2. Recipient encryption key verification
    key_stmt = select(UserKey).where(
        UserKey.id == payload.recipient_encryption_key_id,
        UserKey.user_id == recipient.id,
        UserKey.key_purpose == "encryption",
        UserKey.status == "active",
    )
    encryption_key = (await db.execute(key_stmt)).scalar_one_or_none()
    if not encryption_key:
        raise ValidationException(
            message="Recipient does not have an active registered public encryption key matching the provided ID",
            code="INVALID_ENCRYPTION_KEY",
        )

    # 3. ABAC Policy Verification (if document has an active policy)
    pol_stmt = select(AccessPolicy).where(
        AccessPolicy.document_id == document_id,
        AccessPolicy.status == "active",
    )
    active_policy = (await db.execute(pol_stmt)).scalar_one_or_none()
    if active_policy:
        recipient_attrs = await get_user_effective_attributes(db, recipient.id)
        is_eligible = evaluate_policy(active_policy.policy_ast, recipient_attrs)
        if not is_eligible:
            await record_audit_event(
                db=db,
                event_type="share.grant.denied",
                outcome="denied",
                actor_user_id=owner_user_id,
                document_id=document_id,
                metadata={
                    "recipient_id": str(recipient.id),
                    "policy_id": str(active_policy.id),
                    "reason": "ABAC policy violation",
                },
            )
            raise ForbiddenException(
                message="Recipient does not satisfy document ABAC policy",
                code="ABAC_POLICY_DENIED",
            )

    # 4. Store recipient's wrapped DEK envelope for the document's current version
    try:
        wrapped_bytes = base64.b64decode(payload.wrapped_dek)
    except Exception:
        raise ValidationException("Invalid base64 encoding for wrapped_dek", code="INVALID_WRAPPED_KEY")

    env_stmt = select(DocumentKeyEnvelope).where(
        DocumentKeyEnvelope.document_version_id == doc.current_version_id,
        DocumentKeyEnvelope.recipient_user_id == recipient.id,
        DocumentKeyEnvelope.recipient_encryption_key_id == payload.recipient_encryption_key_id,
    )
    existing_env = (await db.execute(env_stmt)).scalar_one_or_none()
    if existing_env:
        existing_env.wrapped_key = wrapped_bytes
        existing_env.wrapping_algorithm = encryption_key.algorithm or "RSA-OAEP-3072"
        existing_env.status = "active"
        existing_env.revoked_at = None
    else:
        new_env = DocumentKeyEnvelope(
            document_version_id=doc.current_version_id,
            recipient_user_id=recipient.id,
            recipient_encryption_key_id=payload.recipient_encryption_key_id,
            wrapping_algorithm=encryption_key.algorithm or "RSA-OAEP-3072",
            wrapped_key=wrapped_bytes,
            envelope_version=1,
            status="active",
            created_by=owner_user_id,
        )
        db.add(new_env)

    # 5. Create or update AccessGrant
    grant_stmt = select(AccessGrant).where(
        AccessGrant.document_id == document_id,
        AccessGrant.grantee_user_id == recipient.id,
    )
    grant = (await db.execute(grant_stmt)).scalar_one_or_none()
    if grant:
        grant.status = "active"
        grant.permissions = payload.permissions
        grant.expires_at = payload.expires_at
        grant.policy_version_id = active_policy.id if active_policy else None
        grant.revoked_at = None
    else:
        grant = AccessGrant(
            document_id=document_id,
            grantor_user_id=owner_user_id,
            grantee_user_id=recipient.id,
            grant_type="user",
            permissions=payload.permissions,
            policy_version_id=active_policy.id if active_policy else None,
            status="active",
            expires_at=payload.expires_at,
        )
        db.add(grant)

    await db.flush()

    await record_audit_event(
        db=db,
        event_type="share.grant.created",
        outcome="success",
        actor_user_id=owner_user_id,
        document_id=document_id,
        metadata={
            "grant_id": str(grant.id),
            "recipient_id": str(recipient.id),
            "permissions": grant.permissions,
        },
    )

    grant.grantee = recipient
    return _format_grant_response(grant)


async def revoke_grant(
    db: AsyncSession,
    document_id: uuid.UUID,
    grant_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> None:
    """Atomically revoke access grant and all recipient's wrapped key envelopes for the document."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException("Only the document owner can revoke access", code="FORBIDDEN")

    grant_stmt = select(AccessGrant).where(
        AccessGrant.id == grant_id,
        AccessGrant.document_id == document_id,
    )
    grant = (await db.execute(grant_stmt)).scalar_one_or_none()
    if not grant:
        raise NotFoundException("Access grant not found", code="GRANT_NOT_FOUND")

    now = datetime.now(timezone.utc)
    grant.status = "revoked"
    grant.revoked_at = now

    # Revoke all key envelopes for this grantee across all versions of this document
    if grant.grantee_user_id:
        v_subq = select(DocumentVersion.id).where(DocumentVersion.document_id == document_id).scalar_subquery()
        await db.execute(
            update(DocumentKeyEnvelope)
            .where(
                DocumentKeyEnvelope.document_version_id.in_(v_subq),
                DocumentKeyEnvelope.recipient_user_id == grant.grantee_user_id,
                DocumentKeyEnvelope.status == "active",
            )
            .values(status="revoked", revoked_at=now)
        )

    await db.flush()

    await record_audit_event(
        db=db,
        event_type="share.grant.revoked",
        outcome="success",
        actor_user_id=owner_user_id,
        document_id=document_id,
        metadata={"grant_id": str(grant_id), "grantee_id": str(grant.grantee_user_id)},
    )


async def list_document_grants(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> List[AccessGrantResponse]:
    """List all grants (active and revoked) for a document."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException("Only document owner can view grant audit list", code="FORBIDDEN")

    stmt = (
        select(AccessGrant)
        .options(selectinload(AccessGrant.grantee))
        .where(AccessGrant.document_id == document_id)
        .order_by(AccessGrant.created_at.desc())
    )
    grants = (await db.execute(stmt)).scalars().all()
    return [_format_grant_response(g) for g in grants]


async def list_shared_with_me(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[SharedDocumentResponse]:
    """List documents actively shared with the caller."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(AccessGrant)
        .options(
            selectinload(AccessGrant.grantee),
            selectinload(AccessGrant.policy),
            selectinload(AccessGrant.document).selectinload(Document.current_version),
        )
        .join(Document, AccessGrant.document_id == Document.id)
        .where(
            AccessGrant.grantee_user_id == user_id,
            AccessGrant.status == "active",
            Document.status != "deleted",
            or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
        )
        .order_by(AccessGrant.created_at.desc())
    )
    grants = (await db.execute(stmt)).scalars().all()

    shared_items: List[SharedDocumentResponse] = []
    for g in grants:
        doc_resp = _format_document_response(g.document)
        grant_resp = _format_grant_response(g)
        pol_resp = _format_policy_response(g.policy)
        shared_items.append(
            SharedDocumentResponse(
                document=doc_resp,
                grant=grant_resp,
                policy=pol_resp,
            )
        )
    return shared_items


def _format_share_link_response(link: ShareLink) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=link.id,
        access_grant_id=link.access_grant_id,
        created_by=link.created_by,
        status=link.status,
        expires_at=link.expires_at,
        max_uses=link.max_uses,
        use_count=link.use_count,
        created_at=link.created_at,
        revoked_at=link.revoked_at,
    )


async def create_share_link(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    payload: CreateShareLinkRequest,
) -> ShareLinkCreatedResponse:
    """Create a protected share link with client-side wrapped DEK envelope."""
    if not settings.ENABLE_SHARE_LINKS:
        raise ForbiddenException(
            message="Protected share links are disabled pending finalized key-delivery design",
            code="SHARE_LINKS_DISABLED",
        )

    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException("Only the document owner can generate share links", code="FORBIDDEN")

    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        raise ValidationException("Link expiration must be in the future", code="INVALID_EXPIRATION")

    if payload.max_uses is not None and payload.max_uses <= 0:
        raise ValidationException("max_uses must be a positive integer", code="INVALID_MAX_USES")

    try:
        wrapped_dek_bytes = base64.b64decode(payload.wrapped_dek)
    except Exception:
        raise ValidationException("Invalid base64 encoding for wrapped_dek", code="INVALID_WRAPPED_KEY")

    # Generate high-entropy 32-byte URL-safe bearer token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).digest()

    # Active policy version linkage if present
    pol_stmt = (
        select(AccessPolicy)
        .where(AccessPolicy.document_id == document_id, AccessPolicy.status == "active")
        .order_by(AccessPolicy.version_number.desc())
    )
    policy = (await db.execute(pol_stmt)).scalar_one_or_none()

    # Create underlying AccessGrant
    grant = AccessGrant(
        document_id=document_id,
        grantor_user_id=owner_user_id,
        grantee_user_id=None,
        grant_type="link",
        permissions=payload.permissions,
        policy_version_id=policy.id if policy else None,
        status="active",
        expires_at=expires_at,
    )
    db.add(grant)
    await db.flush()

    # Create ShareLink
    share_link = ShareLink(
        access_grant_id=grant.id,
        created_by=owner_user_id,
        token_hash=token_hash,
        token_key_version=1,
        status="active",
        expires_at=expires_at,
        max_uses=payload.max_uses,
        use_count=0,
        wrapped_dek=wrapped_dek_bytes,
    )
    db.add(share_link)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="share.link.created",
        outcome="success",
        actor_user_id=owner_user_id,
        document_id=document_id,
        metadata={
            "link_id": str(share_link.id),
            "access_grant_id": str(grant.id),
            "max_uses": payload.max_uses,
            "expires_at": expires_at.isoformat(),
        },
    )

    return ShareLinkCreatedResponse(
        id=share_link.id,
        access_grant_id=grant.id,
        created_by=owner_user_id,
        status=share_link.status,
        expires_at=share_link.expires_at,
        max_uses=share_link.max_uses,
        use_count=share_link.use_count,
        created_at=share_link.created_at,
        revoked_at=share_link.revoked_at,
        token=token,
    )


async def list_share_links(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> List[ShareLinkResponse]:
    """List all share links (active, revoked, expired) for an owned document."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException("Only the document owner can inspect share links", code="FORBIDDEN")

    stmt = (
        select(ShareLink)
        .join(AccessGrant, ShareLink.access_grant_id == AccessGrant.id)
        .where(AccessGrant.document_id == document_id)
        .order_by(ShareLink.created_at.desc())
    )
    links = (await db.execute(stmt)).scalars().all()
    return [_format_share_link_response(link) for link in links]


async def revoke_share_link(
    db: AsyncSession,
    document_id: uuid.UUID,
    link_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> None:
    """Revoke a share link and its underlying AccessGrant."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if doc.owner_id != owner_user_id:
        raise ForbiddenException("Only the document owner can revoke share links", code="FORBIDDEN")

    stmt = (
        select(ShareLink)
        .options(selectinload(ShareLink.access_grant))
        .join(AccessGrant, ShareLink.access_grant_id == AccessGrant.id)
        .where(ShareLink.id == link_id, AccessGrant.document_id == document_id)
    )
    link = (await db.execute(stmt)).scalar_one_or_none()
    if not link:
        raise NotFoundException("Share link not found", code="SHARE_LINK_NOT_FOUND")

    now = datetime.now(timezone.utc)
    link.status = "revoked"
    link.revoked_at = now
    if link.access_grant:
        link.access_grant.status = "revoked"
        link.access_grant.revoked_at = now
        link.access_grant.revocation_reason = "Link revoked by owner"

    await db.flush()

    await record_audit_event(
        db=db,
        event_type="share.link.revoked",
        outcome="success",
        actor_user_id=owner_user_id,
        document_id=document_id,
        metadata={"link_id": str(link.id), "access_grant_id": str(link.access_grant_id)},
    )


async def redeem_share_link(
    db: AsyncSession,
    token: str,
) -> RedeemShareLinkResponse:
    """Redeem a valid share token, increment use count, and issue short-lived presigned download package."""
    token_hash = hashlib.sha256(token.encode("utf-8")).digest()
    stmt = (
        select(ShareLink)
        .options(
            selectinload(ShareLink.access_grant).selectinload(AccessGrant.document).selectinload(Document.current_version),
        )
        .where(ShareLink.token_hash == token_hash)
    )
    link = (await db.execute(stmt)).scalar_one_or_none()
    if not link:
        raise NotFoundException("Share link not found or invalid", code="SHARE_LINK_NOT_FOUND")

    now = datetime.now(timezone.utc)
    expires_at = link.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if link.status != "active":
        raise ForbiddenException(f"Share link is {link.status}", code="SHARE_LINK_INACTIVE")

    if expires_at <= now:
        link.status = "expired"
        if link.access_grant:
            link.access_grant.status = "expired"
        await db.flush()
        raise ForbiddenException("Share link has expired", code="SHARE_LINK_EXPIRED")

    grant = link.access_grant
    if not grant or grant.status != "active":
        raise ForbiddenException("Underlying grant is inactive or revoked", code="GRANT_INACTIVE")

    doc = grant.document
    if not doc or doc.status != "active":
        raise NotFoundException("Document is deleted or unavailable", code="DOCUMENT_UNAVAILABLE")

    version = doc.current_version
    if not version or version.status != "finalized":
        raise NotFoundException("Active document version not found", code="VERSION_NOT_FOUND")

    if link.max_uses is not None and link.use_count >= link.max_uses:
        link.status = "expired"
        grant.status = "expired"
        await db.flush()
        raise ForbiddenException("Share link maximum redemptions reached", code="SHARE_LINK_EXHAUSTED")

    # Increment use count atomically
    link.use_count += 1
    if link.max_uses is not None and link.use_count >= link.max_uses:
        link.status = "expired"
        grant.status = "expired"

    storage = get_storage_adapter()
    download_url = storage.generate_presigned_download_url(
        object_key=version.object_key,
        expires_in=300,
    )

    await record_audit_event(
        db=db,
        event_type="share.link.redeemed",
        outcome="success",
        actor_user_id=None,
        document_id=doc.id,
        metadata={
            "link_id": str(link.id),
            "use_count": link.use_count,
            "max_uses": link.max_uses,
            "version_id": str(version.id),
        },
    )

    wrapped_dek_str = base64.b64encode(link.wrapped_dek).decode("utf-8") if link.wrapped_dek else ""

    return RedeemShareLinkResponse(
        download_url=download_url,
        expires_in=300,
        object_key=version.object_key,
        wrapped_dek=wrapped_dek_str,
        manifest=version.manifest,
        ciphertext_size_bytes=version.ciphertext_size_bytes,
        ciphertext_sha256_hex=version.ciphertext_sha256.hex(),
        document=_format_document_response(doc),
    )


async def get_document_access_overview(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    is_admin: bool = False,
) -> DocumentAccessOverviewResponse:
    """Retrieve full access overview (policy, user grants, and share links) for owner or admin."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    if not is_admin and doc.owner_id != user_id:
        raise ForbiddenException("Only document owner or admin can view access control overview", code="FORBIDDEN")

    # 1. Active policy
    policy_resp = await get_document_policy(db, document_id, user_id)

    # 2. User grants
    grants_stmt = (
        select(AccessGrant)
        .options(selectinload(AccessGrant.grantee))
        .where(AccessGrant.document_id == document_id, AccessGrant.grant_type == "user")
        .order_by(AccessGrant.created_at.desc())
    )
    grants = (await db.execute(grants_stmt)).scalars().all()
    grant_responses = [_format_grant_response(g) for g in grants]

    # 3. Share links
    links_stmt = (
        select(ShareLink)
        .join(AccessGrant, ShareLink.access_grant_id == AccessGrant.id)
        .where(AccessGrant.document_id == document_id)
        .order_by(ShareLink.created_at.desc())
    )
    links = (await db.execute(links_stmt)).scalars().all()
    link_responses = [_format_share_link_response(link) for link in links]

    return DocumentAccessOverviewResponse(
        policy=policy_resp,
        grants=grant_responses,
        share_links=link_responses,
    )


async def evaluate_candidate_access(
    db: AsyncSession,
    document_id: uuid.UUID,
    candidate_user_id: uuid.UUID,
    caller_id: uuid.UUID,
) -> EvaluateAccessResponse:
    """Evaluate whether candidate user satisfies active ABAC policy and has registered encryption key."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc or doc.status == "deleted":
        raise NotFoundException("Document not found", code="DOCUMENT_NOT_FOUND")

    reasons: List[str] = []

    # 1. Candidate account check
    candidate_stmt = select(User).where(User.id == candidate_user_id)
    candidate = (await db.execute(candidate_stmt)).scalar_one_or_none()
    if not candidate or candidate.status != "active":
        return EvaluateAccessResponse(
            eligible=False,
            reasons=["Candidate user account does not exist or is inactive"],
        )

    # 2. Active encryption key check
    key_stmt = select(UserKey).where(
        UserKey.user_id == candidate_user_id,
        UserKey.key_purpose == "encryption",
        UserKey.status == "active",
    )
    has_key = (await db.execute(key_stmt)).scalar_one_or_none() is not None
    if not has_key:
        reasons.append("Candidate does not have an active public encryption key registered")
    else:
        reasons.append("Candidate has an active encryption key registered")

    # 3. Active ABAC policy evaluation
    pol_stmt = (
        select(AccessPolicy)
        .where(AccessPolicy.document_id == document_id, AccessPolicy.status == "active")
        .order_by(AccessPolicy.version_number.desc())
    )
    policy = (await db.execute(pol_stmt)).scalar_one_or_none()

    policy_passed = True
    if policy:
        attrs = await get_user_effective_attributes(db, candidate_user_id)
        policy_passed = evaluate_policy(policy.policy_ast, attrs, {})
        if not policy_passed:
            reasons.append("Candidate attributes do not satisfy active document ABAC policy")
        else:
            reasons.append("Candidate attributes satisfy active document ABAC policy")
    else:
        reasons.append("No active ABAC policy attached to document (open to designated recipients)")

    eligible = has_key and policy_passed
    return EvaluateAccessResponse(eligible=eligible, reasons=reasons)
