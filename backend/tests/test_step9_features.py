import base64
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit, reset_rate_limiter
from app.models.access import AccessGrant, AccessPolicy, ShareLink
from app.models.attribute import AttributeDefinition, UserAttribute
from app.models.audit import AuditBatch, AuditEvent
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.models.user import User, UserKey, UserRole
from app.storage.adapter import InMemoryStorageAdapter

SAMPLE_RSA_JWK = {
    "kty": "RSA",
    "n": (
        "0vx7agoebGcQSuuPiPSXZzxOdBI47TTU483gb455nuUHiOrMr7BiPCs298450NVGJ7U"
        "tfAU9wk3Kwpx36i61VsEWBnLVureaWYRGUGoI5O655V3C8AvApV7DD624NDTQUsCOUz"
        "HYsmFvpFktQtw4SBXFDDAfgDzA5OmA75stbkW8OV7qU7ZPuv3ghdTQtGoZ675kU7g3T"
    ),
    "e": "AQAB",
}


async def create_user_headers(client: AsyncClient, email: str, role: str = "user") -> tuple[dict, dict]:
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email.split("@")[0], "password": "Password123!Secure"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return data, headers


async def register_encryption_key(client: AsyncClient, headers: dict) -> str:
    res = await client.post(
        "/api/v1/users/me/keys",
        headers=headers,
        json={"key_purpose": "encryption", "algorithm": "RSA-OAEP-3072", "public_key_jwk": SAMPLE_RSA_JWK},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def create_and_finalize_document(client: AsyncClient, headers: dict, storage: InMemoryStorageAdapter) -> tuple[str, str]:
    # 1. Create document
    doc_res = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={"display_name": "Financial Report 2026.pdf", "media_type": "application/pdf"},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # 2. Register key
    enc_id = await register_encryption_key(client, headers)

    # 3. Create version intent
    sha256_hex = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    v_res = await client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": 34,
            "ciphertext_sha256_hex": sha256_hex,
            "manifest": {"iv": "test_iv", "chunks": 1},
        },
    )
    assert v_res.status_code == 201
    ver_data = v_res.json()
    ver_id = ver_data["id"]
    storage.put_bytes(ver_data["object_key"], b"ciphertext_encrypted_content_bytes")

    # 4. Finalize
    wrapped_dek = base64.b64encode(b"owner_dek_secret_envelope").decode("ascii")
    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/finalize",
        headers=headers,
        json={"wrapped_dek": wrapped_dek, "recipient_encryption_key_id": enc_id},
    )
    assert fin_res.status_code == 200
    return doc_id, ver_id


@pytest.mark.asyncio
async def test_rate_limiting_429(async_client: AsyncClient):
    """Test 1: Sliding window rate limit returns 429 TOO_MANY_REQUESTS when exceeded."""
    reset_rate_limiter()

    # Rapidly call login beyond limit (max 10 requests / 60s)
    last_status = 200
    for i in range(12):
        res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@dropsafe.local", "password": "Password123!Secure"},
        )
        last_status = res.status_code
        if last_status == 429:
            data = res.json()
            assert data["error"]["code"] == "TOO_MANY_REQUESTS"
            assert "retry_after_seconds" in data["error"]["details"]
            break

    assert last_status == 429, "Rate limiter did not trigger HTTP 429"
    reset_rate_limiter()


@pytest.mark.asyncio
async def test_cookie_csrf_protection(async_client: AsyncClient):
    """Test 2: Cookie-authenticated unsafe requests from untrusted origins are blocked with 403 CSRF_VIOLATION."""
    # Obtain access cookie
    reg_data, _ = await create_user_headers(async_client, "csrf_user@dropsafe.local")
    access_token = reg_data["access_token"]

    # Cookie auth without Authorization header + malicious Origin
    cookies = {settings.ACCESS_COOKIE_NAME: access_token}
    res = await async_client.post(
        "/api/v1/documents",
        cookies=cookies,
        headers={"Origin": "https://evil-attacker-site.com"},
        json={"display_name": "CSRF Attack Doc"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CSRF_VIOLATION"


@pytest.mark.asyncio
async def test_protected_share_link_lifecycle_and_redemption(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
):
    """Test 3: Full protected share link lifecycle (create, list, redeem, max-uses exhaust, and revoke)."""
    _, owner_headers = await create_user_headers(async_client, "link_owner@dropsafe.local")
    doc_id, _ = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # 1. Create Share Link with max_uses=2
    client_wrapped_dek = base64.b64encode(b"link_wrapped_dek_bytes").decode("ascii")
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)

    create_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/share-links",
        headers=owner_headers,
        json={
            "wrapped_dek": client_wrapped_dek,
            "permissions": ["read", "download"],
            "expires_at": future_time.isoformat(),
            "max_uses": 2,
        },
    )
    assert create_res.status_code == 201, create_res.text
    link_data = create_res.json()
    assert "token" in link_data
    token = link_data["token"]
    link_id = link_data["id"]
    assert link_data["max_uses"] == 2
    assert link_data["use_count"] == 0

    # 2. List Share Links (owner only, never exposes raw token)
    list_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/share-links",
        headers=owner_headers,
    )
    assert list_res.status_code == 200
    links = list_res.json()
    assert len(links) >= 1
    assert any(l["id"] == link_id for l in links)
    assert "token" not in links[0]

    # 3. Redeem Share Link 1st time (succeeds)
    redeem_res_1 = await async_client.post(
        "/api/v1/share-links/redeem",
        json={"token": token},
    )
    assert redeem_res_1.status_code == 200, redeem_res_1.text
    pkg1 = redeem_res_1.json()
    assert "download_url" in pkg1
    assert pkg1["wrapped_dek"] == client_wrapped_dek
    assert pkg1["document"]["id"] == doc_id

    # 4. Redeem Share Link 2nd time (succeeds, exhausts max_uses)
    redeem_res_2 = await async_client.post(
        "/api/v1/share-links/redeem",
        json={"token": token},
    )
    assert redeem_res_2.status_code == 200

    # 5. Redeem Share Link 3rd time -> Denied 403 SHARE_LINK_EXHAUSTED or SHARE_LINK_INACTIVE
    redeem_res_3 = await async_client.post(
        "/api/v1/share-links/redeem",
        json={"token": token},
    )
    assert redeem_res_3.status_code == 403

    # 6. Create another link and revoke it
    create_res_2 = await async_client.post(
        f"/api/v1/documents/{doc_id}/share-links",
        headers=owner_headers,
        json={
            "wrapped_dek": client_wrapped_dek,
            "permissions": ["read", "download"],
            "expires_at": future_time.isoformat(),
        },
    )
    assert create_res_2.status_code == 201
    token_2 = create_res_2.json()["token"]
    link_2_id = create_res_2.json()["id"]

    revoke_res = await async_client.delete(
        f"/api/v1/documents/{doc_id}/share-links/{link_2_id}",
        headers=owner_headers,
    )
    assert revoke_res.status_code == 204

    # Attempting to redeem revoked link returns 403
    redeem_revoked = await async_client.post(
        "/api/v1/share-links/redeem",
        json={"token": token_2},
    )
    assert redeem_revoked.status_code == 403


@pytest.mark.asyncio
async def test_document_metadata_update_and_version_history(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
):
    """Test 4: PATCH /documents/{id} updates metadata and GET /documents/{id}/versions lists history."""
    _, owner_headers = await create_user_headers(async_client, "meta_owner@dropsafe.local")
    doc_id, ver_id = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Update document name
    patch_res = await async_client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=owner_headers,
        json={"display_name": "Renamed Confidential Report.pdf"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["display_name"] == "Renamed Confidential Report.pdf"

    # List versions
    ver_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions",
        headers=owner_headers,
    )
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) == 1
    assert versions[0]["id"] == ver_id
    assert versions[0]["version_number"] == 1


@pytest.mark.asyncio
async def test_multi_recipient_rekeying(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 5: Version finalization supports recipient_envelopes for atomic re-keying on version rotation."""
    _, owner_headers = await create_user_headers(async_client, "owner_rekey@dropsafe.local")
    doc_id, _ = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Register Bob as recipient
    bob_data, bob_headers = await create_user_headers(async_client, "bob_rekey@dropsafe.local")
    bob_id = uuid.UUID(bob_data["user"]["id"])
    bob_enc_id = await register_encryption_key(async_client, bob_headers)
    owner_enc_id = await register_encryption_key(async_client, owner_headers)

    # Create Version 2 Intent
    storage = test_storage
    sha256_hex = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    v2_intent = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=owner_headers,
        json={
            "key_version": 2,
            "ciphertext_size_bytes": 19,
            "ciphertext_sha256_hex": sha256_hex,
            "manifest": {"iv": "v2_iv"},
        },
    )
    assert v2_intent.status_code == 201
    v2_data = v2_intent.json()
    v2_id = v2_data["id"]
    storage.put_bytes(v2_data["object_key"], b"v2_ciphertext_bytes")

    # Finalize v2 with owner envelope + recipient envelope for Bob
    fin_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{v2_id}/finalize",
        headers=owner_headers,
        json={
            "wrapped_dek": base64.b64encode(b"v2_owner_dek").decode(),
            "recipient_encryption_key_id": owner_enc_id,
            "recipient_envelopes": [
                {
                    "recipient_user_id": str(bob_id),
                    "recipient_encryption_key_id": bob_enc_id,
                    "wrapped_dek": base64.b64encode(b"v2_bob_dek").decode(),
                    "wrapping_algorithm": "RSA-OAEP-3072",
                }
            ],
        },
    )
    assert fin_res.status_code == 200

    # Verify both envelopes exist in database
    env_stmt = select(DocumentKeyEnvelope).where(DocumentKeyEnvelope.document_version_id == uuid.UUID(v2_id))
    envelopes = (await db_session.execute(env_stmt)).scalars().all()
    assert len(envelopes) == 2
    recipients = {e.recipient_user_id for e in envelopes}
    assert bob_id in recipients


@pytest.mark.asyncio
async def test_document_access_overview_and_evaluation(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 6: GET /documents/{id}/access and POST /documents/{id}/access/evaluate."""
    _, owner_headers = await create_user_headers(async_client, "access_owner@dropsafe.local")
    doc_id, _ = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Attach policy
    await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=owner_headers,
        json={"policy_ast": {"op": "eq", "attribute": "department", "value": "finance"}},
    )

    # Create candidate user without key or attribute
    cand_data, cand_headers = await create_user_headers(async_client, "cand_test@dropsafe.local")
    cand_id = uuid.UUID(cand_data["user"]["id"])

    # Evaluate candidate -> Not eligible (missing key and fails policy)
    eval_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/access/evaluate",
        headers=owner_headers,
        json={"candidate_user_id": str(cand_id)},
    )
    assert eval_res.status_code == 200
    assert eval_res.json()["eligible"] is False

    # Get access overview
    overview_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/access",
        headers=owner_headers,
    )
    assert overview_res.status_code == 200
    ov = overview_res.json()
    assert ov["policy"] is not None
    assert isinstance(ov["grants"], list)
    assert isinstance(ov["share_links"], list)


@pytest.mark.asyncio
async def test_workspace_overview(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
):
    """Test 7: GET /workspace/overview returns aggregate statistics and recent file history."""
    _, headers = await create_user_headers(async_client, "ws_user@dropsafe.local")
    await create_and_finalize_document(async_client, headers, test_storage)

    ws_res = await async_client.get("/api/v1/workspace/overview", headers=headers)
    assert ws_res.status_code == 200, ws_res.text
    ws = ws_res.json()
    assert ws["owned_documents_count"] >= 1
    assert ws["has_active_encryption_key"] is True
    assert len(ws["recent_documents"]) >= 1


@pytest.mark.asyncio
async def test_admin_user_status_management(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 8: Admin can update user status and cannot disable self."""
    admin_data, admin_headers = await create_user_headers(async_client, "admin_user@dropsafe.local")
    admin_id = uuid.UUID(admin_data["user"]["id"])

    # Give admin role in database
    db_session.add(UserRole(user_id=admin_id, role="admin"))
    await db_session.commit()

    target_data, _ = await create_user_headers(async_client, "target_user@dropsafe.local")
    target_id = target_data["user"]["id"]

    # Disable target user
    dis_res = await async_client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        headers=admin_headers,
        json={"status": "disabled"},
    )
    assert dis_res.status_code == 200
    assert dis_res.json()["status"] == "disabled"

    # Self-disable prevented
    self_res = await async_client.patch(
        f"/api/v1/admin/users/{admin_id}/status",
        headers=admin_headers,
        json={"status": "disabled"},
    )
    assert self_res.status_code == 403


@pytest.mark.asyncio
async def test_audit_batches_anchors_and_verify_chain(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 9: Audit batch listing, anchor inspection, and sequential hash chain verification."""
    _, headers = await create_user_headers(async_client, "audit_chain_test@dropsafe.local")
    await create_and_finalize_document(async_client, headers, test_storage)

    # 1. Verify chain
    chain_res = await async_client.get("/api/v1/audit/verify-chain", headers=headers)
    assert chain_res.status_code == 200
    chain_data = chain_res.json()
    assert chain_data["chain_valid"] is True
    assert chain_data["checked_events"] > 0
    assert chain_data["first_broken_sequence"] is None

    # 2. Trigger Batch creation
    batch_res = await async_client.post("/api/v1/audit-batches", headers=headers)
    assert batch_res.status_code == 201
    batch_data = batch_res.json()
    batch_id = batch_data["id"]

    # 3. List Batches
    list_b_res = await async_client.get("/api/v1/audit-batches", headers=headers)
    assert list_b_res.status_code == 200
    batches = list_b_res.json()
    assert any(b["id"] == batch_id for b in batches)

    # 4. Get Anchors for batch
    anchors_res = await async_client.get(f"/api/v1/audit-batches/{batch_id}/anchors", headers=headers)
    assert anchors_res.status_code == 200
