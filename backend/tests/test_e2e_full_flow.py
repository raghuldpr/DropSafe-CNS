import base64
from datetime import datetime, timedelta, timezone
import hashlib
import uuid
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.issuer_crypto import (
    _b64url_decode,
    _b64url_encode,
    canonicalize_credential_payload,
)
from app.models.attribute import AttributeCredentialSignature, AttributeDefinition, UserAttribute
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.models.user import User, UserKey, UserRole
from app.storage.adapter import InMemoryStorageAdapter
from app.worker.worker import OutboxWorker
import seed


@pytest.mark.asyncio
async def test_complete_dropsafe_e2e_lifecycle(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Unified End-to-End simulation testing all DropSafe cryptographic, ABAC, and ledger boundaries."""

    # =========================================================================
    # STAGE 1: BOOTSTRAP & SEEDING VERIFICATION
    # =========================================================================
    await seed.seed_database()

    # Verify all 4 demo users exist
    demo_emails = [
        "admin@dropsafe.local",
        "alice@dropsafe.local",
        "bob@dropsafe.local",
        "charlie@dropsafe.local",
    ]
    users_stmt = select(User).where(User.email.in_(demo_emails))
    users = (await db_session.execute(users_stmt)).scalars().all()
    user_map = {u.email: u for u in users}
    assert len(user_map) == 4

    admin_user = user_map["admin@dropsafe.local"]
    alice_user = user_map["alice@dropsafe.local"]
    bob_user = user_map["bob@dropsafe.local"]
    charlie_user = user_map["charlie@dropsafe.local"]

    # Verify admin roles
    admin_roles_stmt = select(UserRole.role).where(UserRole.user_id == admin_user.id)
    admin_roles = set((await db_session.execute(admin_roles_stmt)).scalars().all())
    assert "admin" in admin_roles and "user" in admin_roles

    # Verify Alice, Bob, and Charlie attributes
    async def get_user_attrs(user_id: uuid.UUID):
        stmt = (
            select(UserAttribute, AttributeDefinition)
            .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
            .where(UserAttribute.user_id == user_id)
        )
        return {d.name: a.value for a, d in (await db_session.execute(stmt)).all()}

    alice_attrs = await get_user_attrs(alice_user.id)
    assert alice_attrs.get("department") == "engineering"
    assert alice_attrs.get("clearance_level") == 2

    bob_attrs = await get_user_attrs(bob_user.id)
    assert bob_attrs.get("department") == "finance"
    assert bob_attrs.get("clearance_level") == 1

    charlie_attrs = await get_user_attrs(charlie_user.id)
    assert charlie_attrs.get("department") == "engineering"
    assert charlie_attrs.get("is_contractor") is True

    # Verify active keys and signed credentials for each demo user
    for u in [admin_user, alice_user, bob_user, charlie_user]:
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

    # =========================================================================
    # STAGE 2: AUTHENTICATION & SESSION TRANSPORT (ALICE)
    # =========================================================================
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@dropsafe.local", "password": "AlicePass123!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    alice_token = login_data["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    # Verify HttpOnly session cookies
    assert settings.ACCESS_COOKIE_NAME in login_resp.cookies

    # Verify Alice's profile
    me_resp = await async_client.get("/api/v1/users/me", headers=alice_headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "alice@dropsafe.local"
    assert me_data["roles"] == ["user"]
    assert me_data["has_active_encryption_key"] is True
    assert me_data["has_active_signing_key"] is True

    # =========================================================================
    # STAGE 3: KEY DIRECTORY INSPECTION & CREDENTIAL VERIFICATION
    # =========================================================================
    lookup_resp = await async_client.get(
        "/api/v1/users/lookup?email=bob@dropsafe.local",
        headers=alice_headers,
    )
    assert lookup_resp.status_code == 200
    bob_dir = lookup_resp.json()
    assert bob_dir["email"] == "bob@dropsafe.local"
    bob_enc_keys = [k for k in bob_dir["active_keys"] if k["key_purpose"] == "encryption"]
    assert len(bob_enc_keys) == 1
    bob_enc_key_id = bob_enc_keys[0]["id"]
    assert bob_enc_keys[0]["algorithm"] == "RSA-OAEP-3072"

    # Verify Attribute Authority's ECDSA P-256 signature on Bob's credential
    issuer_resp = await async_client.get("/api/v1/users/issuer-public-key", headers=alice_headers)
    assert issuer_resp.status_code == 200
    issuer_jwk = issuer_resp.json()["public_jwk"]
    assert issuer_jwk["crv"] == "P-256"

    # Reconstruct public key from JWK
    issuer_pub_numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(_b64url_decode(issuer_jwk["x"]), "big"),
        int.from_bytes(_b64url_decode(issuer_jwk["y"]), "big"),
        ec.SECP256R1(),
    )
    issuer_pub_key = issuer_pub_numbers.public_key()

    # Fetch Bob's active credential record and verify signature with reconstructed key
    bob_cred_stmt = select(AttributeCredentialSignature).where(
        AttributeCredentialSignature.user_id == bob_user.id,
        AttributeCredentialSignature.status == "active",
    )
    bob_cred = (await db_session.execute(bob_cred_stmt)).scalar_one()
    bob_canonical_bytes = canonicalize_credential_payload(bob_cred.payload)
    # This must not raise InvalidSignature
    issuer_pub_key.verify(bob_cred.signature, bob_canonical_bytes, ec.ECDSA(hashes.SHA256()))

    # =========================================================================
    # STAGE 4: ZERO-KNOWLEDGE ENCRYPTED UPLOAD FLOW (ALICE)
    # =========================================================================
    # 4a. Alice generates and registers an active client-held ECDSA signing keypair
    alice_client_priv = ec.generate_private_key(ec.SECP256R1())
    alice_pub_nums = alice_client_priv.public_key().public_numbers()
    alice_sig_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url_encode(alice_pub_nums.x.to_bytes(32, "big")),
        "y": _b64url_encode(alice_pub_nums.y.to_bytes(32, "big")),
    }
    alice_key_resp = await async_client.post(
        "/api/v1/users/me/keys",
        headers=alice_headers,
        json={
            "key_purpose": "signing",
            "algorithm": "ECDSA-P256",
            "public_key_jwk": alice_sig_jwk,
        },
    )
    assert alice_key_resp.status_code == 201
    alice_signing_key_id = alice_key_resp.json()["id"]

    # 4b. Get Alice's active encryption key ID
    alice_enc_stmt = select(UserKey.id).where(
        UserKey.user_id == alice_user.id,
        UserKey.key_purpose == "encryption",
        UserKey.status == "active",
    )
    alice_enc_key_id = str((await db_session.execute(alice_enc_stmt)).scalar_one())

    # 4c. Alice creates document
    doc_create_resp = await async_client.post(
        "/api/v1/documents",
        headers=alice_headers,
        json={"display_name": "Project_Titan_Financial_Plan.pdf", "media_type": "application/pdf"},
    )
    assert doc_create_resp.status_code == 201
    doc_id = doc_create_resp.json()["id"]

    # 4d. Alice creates version upload intent
    ciphertext_bytes = b"encrypted_aes_gcm_ciphertext_blocks_content_32_bytes_test"
    ciphertext_hash = hashlib.sha256(ciphertext_bytes).digest()

    version_intent_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=alice_headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": len(ciphertext_bytes),
            "ciphertext_sha256_hex": ciphertext_hash.hex(),
            "manifest": {"chunk_size": 65536, "total_chunks": 1},
        },
    )
    assert version_intent_resp.status_code == 201
    version_id = version_intent_resp.json()["id"]
    object_key = version_intent_resp.json()["object_key"]

    # 4e. Alice requests presigned upload URL
    upload_url_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/upload-url",
        headers=alice_headers,
    )
    assert upload_url_resp.status_code == 200
    assert upload_url_resp.json()["object_key"] == object_key

    # 4f. Client uploads ciphertext directly to storage adapter
    test_storage.put_object_bytes(object_key, ciphertext_bytes)

    # 4g. Alice signs ciphertext hash and finalizes version
    alice_signature = alice_client_priv.sign(ciphertext_hash, ec.ECDSA(hashes.SHA256()))
    owner_wrapped_dek = base64.b64encode(b"alice_rsa_wrapped_dek_bytes_here").decode("ascii")

    finalize_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/finalize",
        headers=alice_headers,
        json={
            "wrapped_dek": owner_wrapped_dek,
            "recipient_encryption_key_id": alice_enc_key_id,
            "signature_hex": alice_signature.hex(),
            "signature_algorithm": "ECDSA-P256",
            "signing_key_id": alice_signing_key_id,
        },
    )
    assert finalize_resp.status_code == 200
    doc_final = finalize_resp.json()
    assert doc_final["current_version"]["id"] == version_id
    assert doc_final["current_version"]["status"] == "finalized"

    # =========================================================================
    # STAGE 5: ABAC POLICY ATTACHMENT
    # =========================================================================
    # Alice attaches policy requiring department == 'finance'
    policy_resp = await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=alice_headers,
        json={
            "policy_ast": {
                "op": "eq",
                "attribute": "department",
                "value": "finance",
            }
        },
    )
    assert policy_resp.status_code == 200
    assert policy_resp.json()["policy_ast"]["value"] == "finance"

    # =========================================================================
    # STAGE 6: DUAL-LAYER SHARING ENFORCEMENT
    # =========================================================================
    # 6a. Negative Case: Charlie has department='engineering' -> HTTP 403 Forbidden
    charlie_enc_key_stmt = select(UserKey.id).where(
        UserKey.user_id == charlie_user.id,
        UserKey.key_purpose == "encryption",
        UserKey.status == "active",
    )
    charlie_enc_key_id = str((await db_session.execute(charlie_enc_key_stmt)).scalar_one())

    charlie_grant_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=alice_headers,
        json={
            "grantee_user_id": str(charlie_user.id),
            "permissions": ["read", "download"],
            "wrapped_dek": base64.b64encode(b"wrapped_for_charlie").decode("ascii"),
            "recipient_encryption_key_id": charlie_enc_key_id,
        },
    )
    assert charlie_grant_resp.status_code == 403
    assert charlie_grant_resp.json()["error"]["code"] == "ABAC_POLICY_DENIED"

    # 6b. Positive Case: Bob has department='finance' -> HTTP 201 Created
    bob_wrapped_dek = base64.b64encode(b"bob_wrapped_aes_dek_bytes").decode("ascii")
    bob_grant_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=alice_headers,
        json={
            "grantee_user_id": str(bob_user.id),
            "permissions": ["read", "download"],
            "wrapped_dek": bob_wrapped_dek,
            "recipient_encryption_key_id": bob_enc_key_id,
        },
    )
    assert bob_grant_resp.status_code == 201
    grant_id = bob_grant_resp.json()["id"]

    # =========================================================================
    # STAGE 7: AUTHORIZED DOWNLOAD & DECRYPTION VERIFICATION (BOB)
    # =========================================================================
    bob_login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@dropsafe.local", "password": "BobPass123!"},
    )
    assert bob_login_resp.status_code == 200
    bob_token = bob_login_resp.json()["access_token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Bob lists shared workspace
    shared_resp = await async_client.get("/api/v1/shared-with-me", headers=bob_headers)
    assert shared_resp.status_code == 200
    shared_docs = shared_resp.json()
    assert any(d["document"]["id"] == doc_id for d in shared_docs)

    # Bob requests download URL and wrapped DEK envelope
    bob_dl_resp = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url",
        headers=bob_headers,
    )
    assert bob_dl_resp.status_code == 200
    bob_dl_data = bob_dl_resp.json()
    assert "download_url" in bob_dl_data
    assert bob_dl_data["wrapped_dek"] == bob_wrapped_dek

    # =========================================================================
    # STAGE 8: DYNAMIC ATTRIBUTE REVOCATION DEFENSE
    # =========================================================================
    admin_login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@dropsafe.local", "password": "AdminPass123!"},
    )
    assert admin_login_resp.status_code == 200
    admin_token = admin_login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin reassigns Bob's department to 'marketing'
    admin_attr_resp = await async_client.put(
        f"/api/v1/admin/users/{bob_user.id}/attributes/department",
        headers=admin_headers,
        json={"value": "marketing"},
    )
    assert admin_attr_resp.status_code == 200

    # Bob attempts to download again -> strictly denied with HTTP 403
    bob_blocked_resp = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url",
        headers=bob_headers,
    )
    assert bob_blocked_resp.status_code == 403
    assert bob_blocked_resp.json()["error"]["code"] == "ABAC_POLICY_DENIED"

    # =========================================================================
    # STAGE 9: OWNER ACCESS REVOCATION DEFENSE
    # =========================================================================
    # Admin reverts Bob's department back to 'finance'
    revert_resp = await async_client.put(
        f"/api/v1/admin/users/{bob_user.id}/attributes/department",
        headers=admin_headers,
        json={"value": "finance"},
    )
    assert revert_resp.status_code == 200

    # Alice explicitly revokes Bob's grant
    revoke_resp = await async_client.delete(
        f"/api/v1/documents/{doc_id}/grants/{grant_id}",
        headers=alice_headers,
    )
    assert revoke_resp.status_code == 204

    # Bob attempts download again -> strictly denied with HTTP 403
    bob_grant_denied_resp = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url",
        headers=bob_headers,
    )
    assert bob_grant_denied_resp.status_code == 403

    # =========================================================================
    # STAGE 10: AUDIT LEDGER, MERKLE PROOF & BLOCKCHAIN VERIFICATION
    # =========================================================================
    # Admin queries audit events
    audit_resp = await async_client.get("/api/v1/audit-events", headers=admin_headers)
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    event_types = {e["event_type"] for e in audit_events}
    assert "auth.login.success" in event_types
    assert "document.created" in event_types
    assert "document.version.finalized" in event_types
    assert "share.grant.created" in event_types
    assert "share.grant.revoked" in event_types

    # Find the finalization event
    finalize_event = next(e for e in audit_events if e["event_type"] == "document.version.finalized")
    target_event_id = finalize_event["id"]

    # Trigger batch creation
    batch_resp = await async_client.post("/api/v1/audit-batches", headers=admin_headers)
    assert batch_resp.status_code == 201
    batch_id = batch_resp.json()["id"]

    # Run OutboxWorker one-shot routine to anchor batch
    worker = OutboxWorker(worker_id="test-e2e-worker")
    processed_count = await worker.run_once()
    assert processed_count >= 1

    # Confirm batch is anchored
    anchored_batch_resp = await async_client.get(f"/api/v1/audit-batches/{batch_id}", headers=admin_headers)
    assert anchored_batch_resp.status_code == 200
    assert anchored_batch_resp.json()["status"] == "anchored"

    # Fetch Merkle inclusion proof for finalization event
    proof_resp = await async_client.get(
        f"/api/v1/audit-batches/{batch_id}/proofs/{target_event_id}",
        headers=admin_headers,
    )
    assert proof_resp.status_code == 200
    proof_data = proof_resp.json()
    assert len(proof_data["proof"]) > 0

    # Submit proof to POST /api/v1/audit/verify
    verify_resp = await async_client.post(
        "/api/v1/audit/verify",
        json={
            "leaf_hash_hex": proof_data["leaf_hash_hex"],
            "merkle_root_hex": proof_data["merkle_root_hex"],
            "proof": proof_data["proof"],
        },
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["is_valid"] is True
    assert verify_data["matched_batch_id"] == batch_id

    # Tamper with proof payload (mutate one character in leaf hash)
    tampered_leaf = "00" * 32
    tampered_verify_resp = await async_client.post(
        "/api/v1/audit/verify",
        json={
            "leaf_hash_hex": tampered_leaf,
            "merkle_root_hex": proof_data["merkle_root_hex"],
            "proof": proof_data["proof"],
        },
    )
    assert tampered_verify_resp.status_code == 200
    assert tampered_verify_resp.json()["is_valid"] is False

    # =========================================================================
    # STAGE 11: PROTECTED SHARE LINKS & ACCESS SAFEGUARDS
    # =========================================================================
    # 11a. Alice creates a protected share link with zero-knowledge wrapped DEK
    raw_share_dek = b"share_link_encrypted_key_material_demo"
    wrapped_dek_b64 = base64.b64encode(raw_share_dek).decode("ascii")

    share_link_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/share-links",
        headers=alice_headers,
        json={
            "wrapped_dek": wrapped_dek_b64,
            "max_uses": 2,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    assert share_link_resp.status_code == 201
    share_data = share_link_resp.json()
    assert "token" in share_data
    token = share_data["token"]
    assert share_data["status"] == "active"
    assert share_data["max_uses"] == 2

    # 11b. Charlie redeems the share link
    charlie_login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "charlie@dropsafe.local", "password": "CharliePass123!"},
    )
    assert charlie_login_resp.status_code == 200
    charlie_headers = {"Authorization": f"Bearer {charlie_login_resp.json()['access_token']}"}

    redeem_resp = await async_client.post(
        "/api/v1/share-links/redeem",
        headers=charlie_headers,
        json={"token": token},
    )
    assert redeem_resp.status_code == 200
    redeem_data = redeem_resp.json()
    assert redeem_data["document"]["id"] == doc_id
    assert redeem_data["wrapped_dek"] == wrapped_dek_b64

    # 11c. Safeguard verification: When ENABLE_SHARE_LINKS is False, endpoint returns 403 SHARE_LINKS_DISABLED
    try:
        settings.ENABLE_SHARE_LINKS = False
        blocked_link_resp = await async_client.post(
            f"/api/v1/documents/{doc_id}/share-links",
            headers=alice_headers,
            json={"wrapped_dek": wrapped_dek_b64},
        )
        assert blocked_link_resp.status_code == 403
        assert blocked_link_resp.json()["error"]["code"] == "SHARE_LINKS_DISABLED"
    finally:
        settings.ENABLE_SHARE_LINKS = True

