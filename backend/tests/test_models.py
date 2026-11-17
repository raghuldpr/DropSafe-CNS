import os
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models.access import AccessGrant, AccessPolicy, ShareLink
from app.models.attribute import (
    AttributeCredentialSignature,
    AttributeDefinition,
    UserAttribute,
)
from app.models.audit import AuditBatch, AuditEvent, BlockchainAnchor, OutboxJob
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.models.user import User, UserKey, UserRole

EXPECTED_TABLES = {
    "users",
    "user_roles",
    "user_keys",
    "attribute_definitions",
    "user_attributes",
    "attribute_credential_signatures",
    "documents",
    "document_versions",
    "document_key_envelopes",
    "access_policies",
    "access_grants",
    "share_links",
    "audit_batches",
    "audit_events",
    "blockchain_anchors",
    "outbox_jobs",
}


def test_metadata_has_all_16_tables():
    """Verify that Base.metadata has registered exactly the 16 required tables."""
    registered_tables = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES.issubset(registered_tables), (
        f"Missing tables: {EXPECTED_TABLES - registered_tables}"
    )
    assert len(registered_tables) == 16, f"Expected 16 tables, found {len(registered_tables)}"


@pytest.mark.asyncio
async def test_user_models_crud_and_constraints(db_session: AsyncSession):
    """Test User, UserRole, and UserKey CRUD and integrity constraints."""
    # 1. Create User
    user = User(
        email="alice@dropsafe.local",
        display_name="Alice Crypto",
        password_hash="argon2id$v=19$m=65536,t=3,p=4$dummyhash",
        status="active",
    )
    db_session.add(user)
    await db_session.commit()
    assert user.id is not None
    assert user.created_at is not None

    # 2. Assign UserRole
    role = UserRole(
        user_id=user.id,
        role="admin",
        assigned_by=user.id,
    )
    db_session.add(role)
    await db_session.commit()

    # 3. Add UserKey
    user_key = UserKey(
        user_id=user.id,
        key_purpose="encryption",
        algorithm="RSA-OAEP-3072",
        public_key_jwk={"kty": "RSA", "n": "dummy-modulus", "e": "AQAB"},
        public_key_fingerprint=os.urandom(32),
        key_version=1,
        status="active",
    )
    db_session.add(user_key)
    await db_session.commit()
    assert user_key.id is not None

    # Verify query
    res = await db_session.execute(select(User).where(User.email == "alice@dropsafe.local"))
    queried_user = res.scalar_one()
    assert queried_user.display_name == "Alice Crypto"

    # --- Constraints Testing ---

    # Constraint A: Invalid User status
    async with db_session.begin_nested():
        bad_user = User(
            email="invalid_status@dropsafe.local",
            display_name="Bad Status",
            status="corrupted_status",
        )
        db_session.add(bad_user)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint B: Invalid UserRole role
    async with db_session.begin_nested():
        bad_role = UserRole(
            user_id=user.id,
            role="super_superuser",
        )
        db_session.add(bad_role)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint C: Invalid UserKey key_version (must be > 0)
    async with db_session.begin_nested():
        bad_key_version = UserKey(
            user_id=user.id,
            key_purpose="signing",
            algorithm="ECDSA-P256",
            public_key_jwk={"kty": "EC"},
            public_key_fingerprint=os.urandom(32),
            key_version=0,
        )
        db_session.add(bad_key_version)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint D: Duplicate UserKey (user_id, key_purpose, key_version)
    async with db_session.begin_nested():
        duplicate_key = UserKey(
            user_id=user.id,
            key_purpose="encryption",
            algorithm="RSA-OAEP-3072",
            public_key_jwk={"kty": "RSA"},
            public_key_fingerprint=os.urandom(32),
            key_version=1,  # Duplicate of existing
        )
        db_session.add(duplicate_key)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_attribute_models_crud_and_constraints(db_session: AsyncSession):
    """Test AttributeDefinition, UserAttribute, and AttributeCredentialSignature CRUD and constraints."""
    # Setup admin user
    admin = User(email="admin@dropsafe.local", display_name="Admin")
    target_user = User(email="bob@dropsafe.local", display_name="Bob")
    db_session.add_all([admin, target_user])
    await db_session.commit()

    # 1. AttributeDefinition
    attr_def = AttributeDefinition(
        name="clearance_level",
        value_type="string",
        allowed_values=["Public", "Internal", "Confidential", "Secret"],
        description="Security clearance classification level",
        created_by=admin.id,
    )
    db_session.add(attr_def)
    await db_session.commit()

    # 2. UserAttribute
    now = datetime.now(timezone.utc)
    user_attr = UserAttribute(
        user_id=target_user.id,
        attribute_definition_id=attr_def.id,
        value="Secret",
        assigned_by=admin.id,
        valid_from=now,
        valid_until=now + timedelta(days=365),
    )
    db_session.add(user_attr)
    await db_session.commit()

    # 3. AttributeCredentialSignature
    cred_sig = AttributeCredentialSignature(
        user_id=target_user.id,
        credential_version=1,
        payload={"clearance_level": "Secret", "user_id": str(target_user.id)},
        payload_hash=os.urandom(32),
        signature=os.urandom(64),
        issuer_key_id="issuer-kms-key-v1",
        issued_at=now,
    )
    db_session.add(cred_sig)
    await db_session.commit()

    # --- Constraints Testing ---

    # Constraint A: Invalid value_type on AttributeDefinition
    async with db_session.begin_nested():
        bad_def = AttributeDefinition(
            name="invalid_type_def",
            value_type="float_not_allowed",
            created_by=admin.id,
        )
        db_session.add(bad_def)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint B: Invalid validity window (valid_until <= valid_from)
    async with db_session.begin_nested():
        bad_window_attr = UserAttribute(
            user_id=admin.id,
            attribute_definition_id=attr_def.id,
            value="Internal",
            assigned_by=admin.id,
            valid_from=now,
            valid_until=now - timedelta(seconds=1),  # In the past
        )
        db_session.add(bad_window_attr)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint C: Duplicate UserAttribute (user_id, attribute_definition_id)
    async with db_session.begin_nested():
        duplicate_attr = UserAttribute(
            user_id=target_user.id,
            attribute_definition_id=attr_def.id,
            value="Confidential",
            assigned_by=admin.id,
        )
        db_session.add(duplicate_attr)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint D: Invalid credential_version (must be > 0)
    async with db_session.begin_nested():
        bad_cred_ver = AttributeCredentialSignature(
            user_id=target_user.id,
            credential_version=0,
            payload={},
            payload_hash=os.urandom(32),
            signature=os.urandom(64),
            issuer_key_id="k1",
            issued_at=now,
        )
        db_session.add(bad_cred_ver)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_document_models_crud_and_constraints(db_session: AsyncSession):
    """Test Document, DocumentVersion, and DocumentKeyEnvelope with circular FK."""
    owner = User(email="owner@dropsafe.local", display_name="Owner")
    recipient = User(email="recipient@dropsafe.local", display_name="Recipient")
    db_session.add_all([owner, recipient])
    await db_session.commit()

    recipient_key = UserKey(
        user_id=recipient.id,
        key_purpose="encryption",
        algorithm="RSA-OAEP-3072",
        public_key_jwk={"kty": "RSA"},
        public_key_fingerprint=os.urandom(32),
        key_version=1,
    )
    db_session.add(recipient_key)
    await db_session.commit()

    # 1. Create Document without current_version_id
    doc = Document(
        owner_id=owner.id,
        display_name="financial_q3.pdf.enc",
        media_type="application/pdf",
        status="active",
    )
    db_session.add(doc)
    await db_session.commit()

    # 2. Create DocumentVersion referencing document
    doc_ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        key_version=1,
        object_key="storage/blobs/uuid-hash-v1.bin",
        ciphertext_size_bytes=1048576,
        ciphertext_sha256=os.urandom(32),
        manifest={"algorithm": "AES-256-GCM", "chunk_count": 4},
        signature=os.urandom(64),
        signature_algorithm="ECDSA-P256-SHA256",
        status="finalized",
        created_by=owner.id,
    )
    db_session.add(doc_ver)
    await db_session.commit()

    # 3. Update Document current_version_id (circular FK)
    doc.current_version_id = doc_ver.id
    await db_session.commit()

    # 4. Create DocumentKeyEnvelope
    envelope = DocumentKeyEnvelope(
        document_version_id=doc_ver.id,
        recipient_user_id=recipient.id,
        recipient_encryption_key_id=recipient_key.id,
        wrapping_algorithm="RSA-OAEP-3072",
        wrapped_key=os.urandom(256),
        envelope_version=1,
        created_by=owner.id,
    )
    db_session.add(envelope)
    await db_session.commit()

    # Query back and verify relationships
    res = await db_session.execute(select(Document).where(Document.id == doc.id))
    retrieved_doc = res.scalar_one()
    assert retrieved_doc.current_version_id == doc_ver.id

    # --- Constraints Testing ---

    # Constraint A: Invalid Document status
    async with db_session.begin_nested():
        bad_doc = Document(
            owner_id=owner.id,
            display_name="corrupted.bin",
            status="purged",
        )
        db_session.add(bad_doc)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint B: Invalid DocumentVersion version_number <= 0
    async with db_session.begin_nested():
        bad_ver = DocumentVersion(
            document_id=doc.id,
            version_number=0,
            key_version=1,
            object_key="storage/blobs/bad-ver.bin",
            ciphertext_size_bytes=100,
            ciphertext_sha256=os.urandom(32),
            manifest={},
            created_by=owner.id,
        )
        db_session.add(bad_ver)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint C: Signature parity violation (signature provided without algorithm)
    async with db_session.begin_nested():
        bad_sig_parity = DocumentVersion(
            document_id=doc.id,
            version_number=2,
            key_version=1,
            object_key="storage/blobs/bad-sig.bin",
            ciphertext_size_bytes=100,
            ciphertext_sha256=os.urandom(32),
            manifest={},
            signature=os.urandom(64),
            signature_algorithm=None,  # Parity check failure!
            created_by=owner.id,
        )
        db_session.add(bad_sig_parity)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint D: Duplicate version_number for same document
    async with db_session.begin_nested():
        dup_ver = DocumentVersion(
            document_id=doc.id,
            version_number=1,  # Duplicate of version 1
            key_version=1,
            object_key="storage/blobs/dup-v1.bin",
            ciphertext_size_bytes=100,
            ciphertext_sha256=os.urandom(32),
            manifest={},
            created_by=owner.id,
        )
        db_session.add(dup_ver)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_access_models_crud_and_constraints(db_session: AsyncSession):
    """Test AccessPolicy, AccessGrant, and ShareLink CRUD and constraints."""
    grantor = User(email="grantor@dropsafe.local", display_name="Grantor")
    grantee = User(email="grantee@dropsafe.local", display_name="Grantee")
    db_session.add_all([grantor, grantee])
    await db_session.commit()

    doc = Document(
        owner_id=grantor.id,
        display_name="strategy.enc",
        status="active",
    )
    db_session.add(doc)
    await db_session.commit()

    # 1. AccessPolicy
    policy = AccessPolicy(
        document_id=doc.id,
        version_number=1,
        policy_schema_version="v1",
        policy_ast={
            "rules": [{"effect": "permit", "attribute": "clearance", "gte": "Secret"}]
        },
        created_by=grantor.id,
    )
    db_session.add(policy)
    await db_session.commit()

    # 2. AccessGrant (User grant)
    user_grant = AccessGrant(
        document_id=doc.id,
        grantor_user_id=grantor.id,
        grantee_user_id=grantee.id,
        grant_type="user",
        permissions=["read", "download"],
        policy_version_id=policy.id,
        status="active",
    )
    # 3. AccessGrant (Link grant)
    link_grant = AccessGrant(
        document_id=doc.id,
        grantor_user_id=grantor.id,
        grantee_user_id=None,
        grant_type="link",
        permissions=["read"],
        status="active",
    )
    db_session.add_all([user_grant, link_grant])
    await db_session.commit()

    # 4. ShareLink
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    share_link = ShareLink(
        access_grant_id=link_grant.id,
        created_by=grantor.id,
        token_hash=os.urandom(32),
        token_key_version=1,
        status="active",
        expires_at=expires,
        max_uses=5,
        use_count=0,
    )
    db_session.add(share_link)
    await db_session.commit()
    assert share_link.id is not None

    # --- Constraints Testing ---

    # Constraint A: AccessGrant grantee parity: user grant without grantee_user_id
    async with db_session.begin_nested():
        bad_user_grant = AccessGrant(
            document_id=doc.id,
            grantor_user_id=grantor.id,
            grantee_user_id=None,  # Must not be None for grant_type='user'
            grant_type="user",
            permissions=["read"],
        )
        db_session.add(bad_user_grant)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint B: AccessGrant grantee parity: link grant WITH grantee_user_id
    async with db_session.begin_nested():
        bad_link_grant = AccessGrant(
            document_id=doc.id,
            grantor_user_id=grantor.id,
            grantee_user_id=grantee.id,  # Must be None for grant_type='link'
            grant_type="link",
            permissions=["read"],
        )
        db_session.add(bad_link_grant)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint C: ShareLink max_uses <= 0
    async with db_session.begin_nested():
        bad_share_link = ShareLink(
            access_grant_id=link_grant.id,
            created_by=grantor.id,
            token_hash=os.urandom(32),
            expires_at=expires,
            max_uses=0,  # Must be NULL or > 0
        )
        db_session.add(bad_share_link)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint D: ShareLink use_count < 0
    async with db_session.begin_nested():
        bad_use_count = ShareLink(
            access_grant_id=link_grant.id,
            created_by=grantor.id,
            token_hash=os.urandom(32),
            expires_at=expires,
            use_count=-1,  # Must be >= 0
        )
        db_session.add(bad_use_count)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_audit_models_crud_and_constraints(db_session: AsyncSession):
    """Test AuditBatch, AuditEvent, BlockchainAnchor, and OutboxJob CRUD and constraints."""
    user = User(email="auditor@dropsafe.local", display_name="Auditor")
    db_session.add(user)
    await db_session.commit()

    # 1. AuditBatch
    batch = AuditBatch(
        batch_number=1,
        first_sequence_number=1,
        last_sequence_number=100,
        event_count=100,
        merkle_root=os.urandom(32),
        tree_algorithm="SHA-256-MERKLE-v1",
        status="prepared",
    )
    db_session.add(batch)
    await db_session.commit()

    # 2. AuditEvent
    now = datetime.now(timezone.utc)
    event = AuditEvent(
        sequence_number=1,
        actor_user_id=user.id,
        event_type="document.upload",
        outcome="success",
        occurred_at=now,
        request_id="req-test-1234",
        source_ip_hash=os.urandom(32),
        metadata_payload={"file_size": 2048},
        previous_event_hash=None,
        event_hash=os.urandom(32),
        batch_id=batch.id,
    )
    db_session.add(event)
    await db_session.commit()

    # 3. BlockchainAnchor
    anchor = BlockchainAnchor(
        batch_id=batch.id,
        chain_id=11155111,  # Sepolia
        network_name="Ethereum Sepolia",
        contract_address="0x1234567890abcdef1234567890abcdef12345678",
        transaction_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        block_number=5432100,
        status="confirmed",
        confirmation_count=12,
    )
    db_session.add(anchor)
    await db_session.commit()

    # 4. OutboxJob
    job = OutboxJob(
        job_type="anchor_batch",
        aggregate_id=batch.id,
        status="pending",
        attempt_count=0,
        run_after=now,
    )
    db_session.add(job)
    await db_session.commit()

    # Verify query
    res = await db_session.execute(
        select(AuditEvent).where(AuditEvent.sequence_number == 1)
    )
    retrieved_event = res.scalar_one()
    assert retrieved_event.event_type == "document.upload"
    assert retrieved_event.metadata_payload["file_size"] == 2048

    # --- Constraints Testing ---

    # Constraint A: AuditBatch sequence order (last_sequence_number < first_sequence_number)
    async with db_session.begin_nested():
        bad_batch_order = AuditBatch(
            batch_number=2,
            first_sequence_number=50,
            last_sequence_number=10,  # Invalid order!
            event_count=5,
            merkle_root=os.urandom(32),
        )
        db_session.add(bad_batch_order)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint B: AuditEvent outcome invalid
    async with db_session.begin_nested():
        bad_outcome_event = AuditEvent(
            sequence_number=2,
            event_type="document.delete",
            outcome="unauthorized_outcome",  # Not in ('success', 'denied', 'failure', 'pending')
            occurred_at=now,
            event_hash=os.urandom(32),
        )
        db_session.add(bad_outcome_event)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint C: BlockchainAnchor status invalid
    async with db_session.begin_nested():
        bad_anchor_status = BlockchainAnchor(
            batch_id=batch.id,
            chain_id=1,
            network_name="Mainnet",
            contract_address="0x0",
            status="reverted_unknown",
        )
        db_session.add(bad_anchor_status)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Constraint D: OutboxJob invalid job_type
    async with db_session.begin_nested():
        bad_job = OutboxJob(
            job_type="send_marketing_email",  # Not allowed
            aggregate_id=uuid.uuid4(),
            run_after=now,
        )
        db_session.add(bad_job)
        with pytest.raises(IntegrityError):
            await db_session.flush()
