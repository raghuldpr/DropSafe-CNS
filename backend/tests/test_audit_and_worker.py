import hashlib
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.audit.merkle import (
    build_merkle_tree,
    compute_leaf_hash,
    generate_merkle_proof,
    verify_merkle_proof,
)
from app.models.attribute import AttributeCredentialSignature, AttributeDefinition, UserAttribute
from app.models.audit import AuditBatch, AuditEvent, BlockchainAnchor, OutboxJob
from app.models.user import User, UserKey, UserRole
from app.worker.worker import OutboxWorker
import seed


def test_merkle_tree_basic_and_domain_separation():
    """Verify Merkle tree construction, domain separation prefixes, and proof verification."""
    data_items = [f"event_{i}".encode("utf-8") for i in range(5)]
    leaves = [compute_leaf_hash(d) for d in data_items]

    # Check leaf domain separation: 0x00 prefix
    for item, leaf in zip(data_items, leaves):
        expected_leaf = hashlib.sha256(b"\x00" + item).digest()
        assert leaf == expected_leaf

    root, levels = build_merkle_tree(leaves)
    assert len(root) == 32
    assert len(levels) > 1

    # Verify proofs for each leaf
    for idx, leaf in enumerate(leaves):
        proof = generate_merkle_proof(idx, levels)
        assert len(proof) > 0
        is_valid = verify_merkle_proof(leaf, proof, root)
        assert is_valid is True


def test_merkle_proof_tampering():
    """Verify that tampered leaves or modified proofs fail verification."""
    leaves = [compute_leaf_hash(f"leaf_{i}".encode("utf-8")) for i in range(4)]
    root, levels = build_merkle_tree(leaves)

    proof = generate_merkle_proof(0, levels)
    assert verify_merkle_proof(leaves[0], proof, root) is True

    # 1. Tampered leaf data
    tampered_leaf = compute_leaf_hash(b"tampered")
    assert verify_merkle_proof(tampered_leaf, proof, root) is False

    # 2. Tampered proof sibling hash
    tampered_proof = [
        {"position": p["position"], "hash_hex": "00" * 32} if i == 0 else p
        for i, p in enumerate(proof)
    ]
    assert verify_merkle_proof(leaves[0], tampered_proof, root) is False

    # 3. Altered direction
    tampered_dir_proof = [
        {"position": "right" if p["position"] == "left" else "left", "hash_hex": p["hash_hex"]}
        if i == 0 else p
        for i, p in enumerate(proof)
    ]
    assert verify_merkle_proof(leaves[0], tampered_dir_proof, root) is False


@pytest.mark.asyncio
async def test_audit_event_hash_chain_and_sanitization(db_session: AsyncSession):
    """Verify append-only hash chaining and credential sanitization."""
    # Record event 1
    ev1 = await audit_service.record_audit_event(
        db=db_session,
        event_type="test.event.one",
        outcome="success",
        metadata={
            "normal_field": "val1",
            "password": "SecretPassword123!",
            "access_token": "jwt.secret.token",
        },
    )
    await db_session.commit()

    assert ev1.sequence_number == 1
    assert ev1.previous_event_hash is None
    assert "password" not in ev1.metadata_payload
    assert "access_token" not in ev1.metadata_payload
    assert ev1.metadata_payload["normal_field"] == "val1"

    # Record event 2
    ev2 = await audit_service.record_audit_event(
        db=db_session,
        event_type="test.event.two",
        outcome="success",
        metadata={"info": "second event"},
    )
    await db_session.commit()

    assert ev2.sequence_number == 2
    assert ev2.previous_event_hash == ev1.event_hash

    # Record event 3
    ev3 = await audit_service.record_audit_event(
        db=db_session,
        event_type="test.event.three",
        outcome="denied",
    )
    await db_session.commit()

    assert ev3.sequence_number == 3
    assert ev3.previous_event_hash == ev2.event_hash


@pytest.mark.asyncio
async def test_create_audit_batch_and_outbox_job(db_session: AsyncSession):
    """Verify batch creation aggregates unbatched events and enqueues anchoring outbox job."""
    for i in range(5):
        await audit_service.record_audit_event(
            db=db_session,
            event_type=f"batch.event.{i}",
            outcome="success",
        )
    await db_session.commit()

    batch_resp = await audit_service.create_audit_batch(db_session, max_events=5)
    await db_session.commit()

    assert batch_resp is not None
    assert batch_resp.batch_number == 1
    assert batch_resp.event_count == 5
    assert batch_resp.first_sequence_number == 1
    assert batch_resp.last_sequence_number == 5
    assert batch_resp.status == "prepared"

    # Check AuditEvent batch_id assignment
    events_stmt = select(AuditEvent).where(AuditEvent.batch_id == batch_resp.id)
    batched_events = (await db_session.execute(events_stmt)).scalars().all()
    assert len(batched_events) == 5

    # Check OutboxJob creation
    job_stmt = select(OutboxJob).where(OutboxJob.aggregate_id == batch_resp.id)
    job = (await db_session.execute(job_stmt)).scalar_one_or_none()
    assert job is not None
    assert job.job_type == "anchor_batch"
    assert job.status == "pending"


@pytest.mark.asyncio
async def test_audit_api_endpoints_and_permissions(async_client: AsyncClient, db_session: AsyncSession):
    """Verify RBAC and IDOR filtering on audit-events endpoints."""
    # Register admin
    adm_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "admin_audit@example.com", "password": "AdminPassword123!", "display_name": "Admin"},
    )
    assert adm_resp.status_code == 201
    admin_id = uuid.UUID(adm_resp.json()["user"]["id"])
    admin_token = adm_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Grant admin role
    db_session.add(UserRole(user_id=admin_id, role="admin"))
    await db_session.commit()

    # Register regular user
    user_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "user_audit@example.com", "password": "UserPassword123!", "display_name": "User"},
    )
    assert user_resp.status_code == 201
    user_id = uuid.UUID(user_resp.json()["user"]["id"])
    user_token = user_resp.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Record system event and user event
    ev_user = await audit_service.record_audit_event(
        db=db_session,
        event_type="user.action",
        outcome="success",
        actor_user_id=user_id,
    )
    ev_sys = await audit_service.record_audit_event(
        db=db_session,
        event_type="system.internal",
        outcome="success",
        actor_user_id=None,
    )
    await db_session.commit()

    # User queries audit events: sees only user event
    r = await async_client.get("/api/v1/audit-events", headers=user_headers)
    assert r.status_code == 200
    user_events = r.json()
    user_event_ids = [e["id"] for e in user_events]
    assert str(ev_user.id) in user_event_ids
    assert str(ev_sys.id) not in user_event_ids

    # User tries to access system event directly: 404
    r_detail_forbidden = await async_client.get(f"/api/v1/audit-events/{ev_sys.id}", headers=user_headers)
    assert r_detail_forbidden.status_code == 404

    # Admin queries audit events: sees both
    r_admin = await async_client.get("/api/v1/audit-events", headers=admin_headers)
    assert r_admin.status_code == 200
    admin_events = r_admin.json()
    admin_event_ids = [e["id"] for e in admin_events]
    assert str(ev_user.id) in admin_event_ids
    assert str(ev_sys.id) in admin_event_ids


@pytest.mark.asyncio
async def test_audit_batch_proof_and_verification_api(async_client: AsyncClient, db_session: AsyncSession):
    """Verify Merkle inclusion proof retrieval and verification API endpoints."""
    # Register admin user
    adm_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "batch_tester@example.com", "password": "Password123!", "display_name": "Tester"},
    )
    assert adm_resp.status_code == 201
    admin_id = uuid.UUID(adm_resp.json()["user"]["id"])
    db_session.add(UserRole(user_id=admin_id, role="admin"))
    await db_session.commit()
    headers = {"Authorization": f"Bearer {adm_resp.json()['access_token']}"}

    # Record 4 events
    events = []
    for i in range(4):
        ev = await audit_service.record_audit_event(
            db=db_session,
            event_type=f"batch.test.ev.{i}",
            outcome="success",
            actor_user_id=admin_id,
        )
        events.append(ev)
    await db_session.commit()

    # Trigger batch creation
    b_resp = await async_client.post("/api/v1/audit-batches", headers=headers)
    assert b_resp.status_code == 201
    batch_data = b_resp.json()
    batch_id = batch_data["id"]
    merkle_root_hex = batch_data["merkle_root_hex"]

    # Retrieve batch details
    r_batch = await async_client.get(f"/api/v1/audit-batches/{batch_id}", headers=headers)
    assert r_batch.status_code == 200
    assert r_batch.json()["id"] == batch_id

    # Retrieve proof for event 1
    target_event = events[1]
    r_proof = await async_client.get(
        f"/api/v1/audit-batches/{batch_id}/proofs/{target_event.id}",
        headers=headers,
    )
    assert r_proof.status_code == 200
    proof_data = r_proof.json()
    assert proof_data["batch_id"] == batch_id
    assert proof_data["event_id"] == str(target_event.id)
    assert proof_data["merkle_root_hex"] == merkle_root_hex
    assert len(proof_data["proof"]) > 0

    # Verify proof via POST /api/v1/audit/verify
    verify_payload = {
        "leaf_hash_hex": proof_data["leaf_hash_hex"],
        "merkle_root_hex": proof_data["merkle_root_hex"],
        "proof": proof_data["proof"],
    }
    r_verify = await async_client.post("/api/v1/audit/verify", json=verify_payload)
    assert r_verify.status_code == 200
    res = r_verify.json()
    assert res["is_valid"] is True
    assert res["matched_batch_id"] == batch_id

    # Verify tampered proof fails
    tampered_verify = dict(verify_payload)
    tampered_verify["leaf_hash_hex"] = "aa" * 32
    r_tampered = await async_client.post("/api/v1/audit/verify", json=tampered_verify)
    assert r_tampered.status_code == 200
    assert r_tampered.json()["is_valid"] is False


@pytest.mark.asyncio
async def test_outbox_worker_processes_anchoring(db_session: AsyncSession):
    """Verify OutboxWorker claims and processes anchor_batch jobs."""
    # Record event and create batch
    ev = await audit_service.record_audit_event(
        db=db_session,
        event_type="worker.test.event",
        outcome="success",
    )
    await db_session.commit()

    batch_resp = await audit_service.create_audit_batch(db_session, max_events=1)
    await db_session.commit()
    assert batch_resp is not None

    worker = OutboxWorker(worker_id="test-worker")
    processed = await worker.run_once()
    assert processed >= 1

    # Verify job succeeded
    job_stmt = select(OutboxJob).where(OutboxJob.aggregate_id == batch_resp.id)
    job = (await db_session.execute(job_stmt)).scalar_one()
    assert job.status == "succeeded"

    # Verify AuditBatch status is now anchored
    b_stmt = select(AuditBatch).where(AuditBatch.id == batch_resp.id)
    batch = (await db_session.execute(b_stmt)).scalar_one()
    assert batch.status == "anchored"
    assert batch.anchored_at is not None

    # Verify BlockchainAnchor record created
    anchor_stmt = select(BlockchainAnchor).where(BlockchainAnchor.batch_id == batch.id)
    anchor = (await db_session.execute(anchor_stmt)).scalar_one_or_none()
    assert anchor is not None
    assert anchor.status == "confirmed"
    assert anchor.transaction_hash.startswith("0x")
    assert anchor.chain_id == 11155111


@pytest.mark.asyncio
async def test_seed_script_idempotency(db_session: AsyncSession):
    """Verify seed script creates demo users, keys, attributes, and signatures idempotently."""
    # First seed run
    await seed.run_seed()

    # Verify demo users exist
    users_stmt = select(User)
    users = (await db_session.execute(users_stmt)).scalars().all()
    user_emails = {u.email for u in users}
    assert "admin@dropsafe.local" in user_emails
    assert "alice@dropsafe.local" in user_emails
    assert "bob@dropsafe.local" in user_emails
    assert "charlie@dropsafe.local" in user_emails

    # Verify Alice attributes
    alice = next(u for u in users if u.email == "alice@dropsafe.local")
    attrs_stmt = (
        select(UserAttribute, AttributeDefinition)
        .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
        .where(UserAttribute.user_id == alice.id)
    )
    alice_attrs = {d.name: a.value for a, d in (await db_session.execute(attrs_stmt)).all()}
    assert alice_attrs["department"] == "engineering"
    assert alice_attrs["clearance_level"] == 2

    # Verify Charlie attributes
    charlie = next(u for u in users if u.email == "charlie@dropsafe.local")
    c_stmt = (
        select(UserAttribute, AttributeDefinition)
        .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
        .where(UserAttribute.user_id == charlie.id)
    )
    charlie_attrs = {d.name: a.value for a, d in (await db_session.execute(c_stmt)).all()}
    assert charlie_attrs["department"] == "engineering"
    assert charlie_attrs["is_contractor"] is True

    # Verify keys and credential signatures
    for u in users:
        k_stmt = select(UserKey).where(UserKey.user_id == u.id, UserKey.status == "active")
        active_keys = (await db_session.execute(k_stmt)).scalars().all()
        purposes = {k.key_purpose for k in active_keys}
        assert "encryption" in purposes
        assert "signing" in purposes

        cred_stmt = select(AttributeCredentialSignature).where(
            AttributeCredentialSignature.user_id == u.id,
            AttributeCredentialSignature.status == "active",
        )
        cred = (await db_session.execute(cred_stmt)).scalar_one_or_none()
        assert cred is not None
        assert cred.signature is not None

    # Second seed run (must be completely idempotent and not crash)
    await seed.run_seed()

    # Re-verify total count of users didn't double
    users_after = (await db_session.execute(select(User))).scalars().all()
    assert len(users_after) == 4
