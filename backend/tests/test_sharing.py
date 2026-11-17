import base64
import hashlib
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.access import AccessGrant, AccessPolicy
from app.models.attribute import AttributeDefinition, UserAttribute
from app.models.audit import AuditEvent
from app.models.document import DocumentKeyEnvelope
from app.models.user import UserRole
from app.storage.adapter import InMemoryStorageAdapter

SAMPLE_RSA_ENCRYPTION_JWK = {
    "kty": "RSA",
    "n": (
        "0vx7agoebGcQSuuPiPSXZzxOdBI47TTU483gb455nuUHiOrMr7BiPCs298450NVGJ7U"
        "tfAU9wk3Kwpx36i61VsEWBnLVureaWYRGUGoI5O655V3C8AvApV7DD624NDTQUsCOUz"
        "HYsmFvpFktQtw4SBXFDDAfgDzA5OmA75stbkW8OV7qU7ZPuv3ghdTQtGoZ675kU7g3T"
    ),
    "e": "AQAB",
}


async def create_user_and_headers(
    client: AsyncClient,
    email: str,
    display_name: str = "Test User",
) -> tuple[dict, dict]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": display_name},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return data, headers


async def register_encryption_key(client: AsyncClient, headers: dict) -> str:
    r = await client.post(
        "/api/v1/users/me/keys",
        headers=headers,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def create_and_finalize_document(
    client: AsyncClient,
    headers: dict,
    test_storage: InMemoryStorageAdapter,
    name: str = "doc.pdf",
) -> tuple[str, str]:
    """Helper to create, upload, and finalize a document, returning (doc_id, version_id)."""
    enc_id = await register_encryption_key(client, headers)

    doc = (await client.post("/api/v1/documents", headers=headers, json={"display_name": name})).json()
    doc_id = doc["id"]

    data = b"confidential_file_bytes_12345"
    sha = hashlib.sha256(data).hexdigest()

    ver = (await client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": len(data),
            "ciphertext_sha256_hex": sha,
            "manifest": {"chunk_size": 512},
        },
    )).json()
    ver_id = ver["id"]

    # Put in storage
    test_storage.put_object_bytes(ver["object_key"], data)

    # Finalize
    wrapped_dek = base64.b64encode(b"owner_wrapped_dek_key").decode("ascii")
    r_fin = await client.post(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/finalize",
        headers=headers,
        json={
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": enc_id,
        },
    )
    assert r_fin.status_code == 200, r_fin.text
    return doc_id, ver_id


async def setup_attribute_catalog_and_assign(
    client: AsyncClient,
    db: AsyncSession,
    user_id: uuid.UUID,
    attribute_name: str,
    value: str,
) -> None:
    """Helper to ensure definition exists and assign attribute to target user."""
    # Find or create definition
    stmt = select(AttributeDefinition).where(AttributeDefinition.name == attribute_name)
    attr_def = (await db.execute(stmt)).scalar_one_or_none()
    if not attr_def:
        attr_def = AttributeDefinition(
            name=attribute_name,
            value_type="string",
            is_active=True,
            created_by=user_id,
        )
        db.add(attr_def)
        await db.flush()

    user_attr = UserAttribute(
        user_id=user_id,
        attribute_definition_id=attr_def.id,
        value=value,
        assigned_by=user_id,
        source="admin",
    )
    db.add(user_attr)
    await db.commit()


@pytest.mark.asyncio
async def test_set_and_get_document_abac_policy(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
):
    """Test 1: Document owner can set and retrieve an ABAC access policy AST."""
    _, owner_headers = await create_user_and_headers(async_client, "policy_owner@dropsafe.com", "Policy Owner")
    doc_id, _ = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # 1. Attach policy requiring department == 'finance'
    policy_ast = {"op": "eq", "attribute": "department", "value": "finance"}
    r_put = await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=owner_headers,
        json={"policy_ast": policy_ast},
    )
    assert r_put.status_code == 200
    p_data = r_put.json()
    assert p_data["version_number"] == 1
    assert p_data["status"] == "active"
    assert p_data["policy_ast"] == policy_ast

    # 2. Get policy
    r_get = await async_client.get(f"/api/v1/documents/{doc_id}/policy", headers=owner_headers)
    assert r_get.status_code == 200
    assert r_get.json()["id"] == p_data["id"]
    assert r_get.json()["policy_ast"] == policy_ast


@pytest.mark.asyncio
async def test_sharing_rejected_when_recipient_fails_abac_policy(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 2: Sharing with a recipient who fails the ABAC policy is rejected with HTTP 403."""
    _, owner_headers = await create_user_and_headers(async_client, "owner_share1@dropsafe.com")
    doc_id, _ = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Attach policy requiring department == 'finance'
    await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=owner_headers,
        json={"policy_ast": {"op": "eq", "attribute": "department", "value": "finance"}},
    )

    # Recipient Bob (department = 'engineering')
    bob_data, bob_headers = await create_user_and_headers(async_client, "bob.engineer@dropsafe.com", "Bob Engineer")
    bob_id = uuid.UUID(bob_data["user"]["id"])
    bob_enc_id = await register_encryption_key(async_client, bob_headers)

    # Assign department = 'engineering' to Bob
    await setup_attribute_catalog_and_assign(async_client, db_session, bob_id, "department", "engineering")

    # Owner attempts to share with Bob -> Must fail with HTTP 403 ABAC_POLICY_DENIED
    wrapped_dek = base64.b64encode(b"wrapped_for_bob").decode("ascii")
    r_grant = await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=owner_headers,
        json={
            "grantee_user_id": str(bob_id),
            "permissions": ["read", "download"],
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": bob_enc_id,
        },
    )
    assert r_grant.status_code == 403
    assert r_grant.json()["error"]["code"] == "ABAC_POLICY_DENIED"


@pytest.mark.asyncio
async def test_sharing_succeeds_for_eligible_recipient_and_creates_envelope(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 3: Sharing with an eligible recipient succeeds, creates AccessGrant and DocumentKeyEnvelope."""
    _, owner_headers = await create_user_and_headers(async_client, "owner_share2@dropsafe.com")
    doc_id, ver_id = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Attach policy requiring department == 'finance'
    await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=owner_headers,
        json={"policy_ast": {"op": "eq", "attribute": "department", "value": "finance"}},
    )

    # Recipient Carol (department = 'finance')
    carol_data, carol_headers = await create_user_and_headers(async_client, "carol.finance@dropsafe.com", "Carol Finance")
    carol_id = uuid.UUID(carol_data["user"]["id"])
    carol_enc_id = await register_encryption_key(async_client, carol_headers)

    # Assign department = 'finance' to Carol
    await setup_attribute_catalog_and_assign(async_client, db_session, carol_id, "department", "finance")

    # Owner shares with Carol -> Must succeed with HTTP 201
    wrapped_dek = base64.b64encode(b"wrapped_for_carol").decode("ascii")
    r_grant = await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=owner_headers,
        json={
            "grantee_user_id": str(carol_id),
            "permissions": ["read", "download"],
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": carol_enc_id,
        },
    )
    assert r_grant.status_code == 201
    grant_data = r_grant.json()
    assert grant_data["document_id"] == doc_id
    assert grant_data["grantee_user_id"] == str(carol_id)
    assert grant_data["status"] == "active"
    grant_id = grant_data["id"]

    # Verify DocumentKeyEnvelope exists for Carol
    env_stmt = select(DocumentKeyEnvelope).where(
        DocumentKeyEnvelope.document_version_id == uuid.UUID(ver_id),
        DocumentKeyEnvelope.recipient_user_id == carol_id,
    )
    env = (await db_session.execute(env_stmt)).scalar_one_or_none()
    assert env is not None
    assert env.wrapped_key == b"wrapped_for_carol"
    assert env.status == "active"

    # Verify audit event recorded
    audit_stmt = select(AuditEvent).where(AuditEvent.event_type == "share.grant.created")
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_recipient_shared_workspace_and_download_flow(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 4: Eligible recipient can list file in 'Shared With Me' and retrieve download URL + wrapped DEK."""
    _, owner_headers = await create_user_and_headers(async_client, "owner_share3@dropsafe.com")
    doc_id, ver_id = await create_and_finalize_document(async_client, owner_headers, test_storage, name="Financial_Plan.pdf")

    # Policy: department == 'finance'
    await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=owner_headers,
        json={"policy_ast": {"op": "eq", "attribute": "department", "value": "finance"}},
    )

    # Recipient
    recip_data, recip_headers = await create_user_and_headers(async_client, "recip1@dropsafe.com", "Recipient One")
    recip_id = uuid.UUID(recip_data["user"]["id"])
    recip_enc_id = await register_encryption_key(async_client, recip_headers)
    await setup_attribute_catalog_and_assign(async_client, db_session, recip_id, "department", "finance")

    # Share
    wrapped_dek = base64.b64encode(b"recipient_dek_envelope").decode("ascii")
    await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=owner_headers,
        json={
            "grantee_user_id": str(recip_id),
            "permissions": ["read", "download"],
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": recip_enc_id,
        },
    )

    # 1. Recipient calls GET /api/v1/shared-with-me
    r_shared = await async_client.get("/api/v1/shared-with-me", headers=recip_headers)
    assert r_shared.status_code == 200
    shared_list = r_shared.json()
    assert len(shared_list) == 1
    assert shared_list[0]["document"]["id"] == doc_id
    assert shared_list[0]["document"]["display_name"] == "Financial_Plan.pdf"
    assert shared_list[0]["grant"]["status"] == "active"

    # 2. Recipient calls GET download-url
    r_dl = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/download-url",
        headers=recip_headers,
    )
    assert r_dl.status_code == 200
    dl_data = r_dl.json()
    assert "download_url" in dl_data
    assert dl_data["wrapped_dek"] == wrapped_dek
    assert dl_data["recipient_encryption_key_id"] == recip_enc_id


@pytest.mark.asyncio
async def test_attribute_change_revokes_abac_access_dynamically(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 5: If recipient's attributes change, subsequent download attempts are dynamically denied (HTTP 403)."""
    _, owner_headers = await create_user_and_headers(async_client, "owner_share4@dropsafe.com")
    doc_id, ver_id = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Policy: department == 'finance'
    await async_client.put(
        f"/api/v1/documents/{doc_id}/policy",
        headers=owner_headers,
        json={"policy_ast": {"op": "eq", "attribute": "department", "value": "finance"}},
    )

    # Recipient
    recip_data, recip_headers = await create_user_and_headers(async_client, "attr_change_user@dropsafe.com")
    recip_id = uuid.UUID(recip_data["user"]["id"])
    recip_enc_id = await register_encryption_key(async_client, recip_headers)
    await setup_attribute_catalog_and_assign(async_client, db_session, recip_id, "department", "finance")

    # Share
    wrapped_dek = base64.b64encode(b"recipient_dek_envelope").decode("ascii")
    await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=owner_headers,
        json={
            "grantee_user_id": str(recip_id),
            "permissions": ["read", "download"],
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": recip_enc_id,
        },
    )

    # Recipient can download initially
    r_ok = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/download-url",
        headers=recip_headers,
    )
    assert r_ok.status_code == 200

    # Admin changes recipient's department to 'marketing' (fails ABAC policy)
    attr_stmt = select(UserAttribute).where(UserAttribute.user_id == recip_id)
    user_attr = (await db_session.execute(attr_stmt)).scalar_one()
    user_attr.value = "marketing"
    await db_session.commit()

    # Recipient attempts download again -> Denied with HTTP 403 ABAC_POLICY_DENIED
    r_denied = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/download-url",
        headers=recip_headers,
    )
    assert r_denied.status_code == 403
    assert r_denied.json()["error"]["code"] == "ABAC_POLICY_DENIED"


@pytest.mark.asyncio
async def test_owner_access_revocation_blocks_subsequent_downloads(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 6: Owner revokes access via DELETE /grants/{grant_id}, immediately blocking subsequent downloads."""
    _, owner_headers = await create_user_and_headers(async_client, "owner_share5@dropsafe.com")
    doc_id, ver_id = await create_and_finalize_document(async_client, owner_headers, test_storage)

    # Recipient
    recip_data, recip_headers = await create_user_and_headers(async_client, "revoked_user@dropsafe.com")
    recip_id = uuid.UUID(recip_data["user"]["id"])
    recip_enc_id = await register_encryption_key(async_client, recip_headers)

    # Share
    wrapped_dek = base64.b64encode(b"recipient_dek_envelope").decode("ascii")
    r_grant = await async_client.post(
        f"/api/v1/documents/{doc_id}/grants",
        headers=owner_headers,
        json={
            "grantee_user_id": str(recip_id),
            "permissions": ["read", "download"],
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": recip_enc_id,
        },
    )
    assert r_grant.status_code == 201
    grant_id = r_grant.json()["id"]

    # Verify recipient can download before revocation
    r_before = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/download-url",
        headers=recip_headers,
    )
    assert r_before.status_code == 200

    # Owner revokes grant
    r_revoke = await async_client.delete(
        f"/api/v1/documents/{doc_id}/grants/{grant_id}",
        headers=owner_headers,
    )
    assert r_revoke.status_code == 204

    # Recipient attempts download after revocation -> Denied with HTTP 403 ACCESS_REVOKED
    r_after = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{ver_id}/download-url",
        headers=recip_headers,
    )
    assert r_after.status_code == 403
    assert r_after.json()["error"]["code"] == "ACCESS_REVOKED"


@pytest.mark.asyncio
async def test_share_links_disabled_safeguard(async_client: AsyncClient, monkeypatch):
    """Test 7: Attempting to create share links when ENABLE_SHARE_LINKS=False returns HTTP 403."""
    monkeypatch.setattr(settings, "ENABLE_SHARE_LINKS", False)
    _, owner_headers = await create_user_and_headers(async_client, "link_test_owner@dropsafe.com")
    fake_doc_id = str(uuid.uuid4())

    r_link = await async_client.post(
        f"/api/v1/documents/{fake_doc_id}/share-links",
        headers=owner_headers,
    )
    assert r_link.status_code == 403
    assert r_link.json()["error"]["code"] == "SHARE_LINKS_DISABLED"
