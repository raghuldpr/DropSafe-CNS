import base64
import hashlib
import uuid
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.storage.adapter import InMemoryStorageAdapter

# Valid RFC 7517 public JWK for RSA encryption key
SAMPLE_RSA_ENCRYPTION_JWK = {
    "kty": "RSA",
    "n": (
        "0vx7agoebGcQSuuPiPSXZzxOdBI47TTU483gb455nuUHiOrMr7BiPCs298450NVGJ7U"
        "tfAU9wk3Kwpx36i61VsEWBnLVureaWYRGUGoI5O655V3C8AvApV7DD624NDTQUsCOUz"
        "HYsmFvpFktQtw4SBXFDDAfgDzA5OmA75stbkW8OV7qU7ZPuv3ghdTQtGoZ675kU7g3T"
    ),
    "e": "AQAB",
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


async def create_user_and_headers(
    client: AsyncClient,
    email: str,
    display_name: str = "Test User",
) -> tuple[dict, dict]:
    """Helper to register user and return user data and auth headers."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": display_name},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return data, headers


@pytest.mark.asyncio
async def test_document_creation_and_version_intent(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 1: Document creation and version upload intent generation."""
    _, headers = await create_user_and_headers(async_client, "owner1@dropsafe.com", "Owner One")

    # 1. Create document root
    doc_payload = {
        "display_name": "Quarterly_Financial_Report.pdf",
        "media_type": "application/pdf",
    }
    r_create = await async_client.post("/api/v1/documents", headers=headers, json=doc_payload)
    assert r_create.status_code == 201
    doc_data = r_create.json()
    assert doc_data["display_name"] == "Quarterly_Financial_Report.pdf"
    assert doc_data["media_type"] == "application/pdf"
    assert doc_data["status"] == "active"
    assert doc_data["current_version"] is None
    doc_id = doc_data["id"]

    # 2. Create version upload intent
    sha256_dummy = hashlib.sha256(b"encrypted_ciphertext_content").hexdigest()
    version_payload = {
        "key_version": 1,
        "ciphertext_size_bytes": 1024,
        "ciphertext_sha256_hex": sha256_dummy,
        "manifest": {
            "chunk_size": 65536,
            "total_chunks": 1,
            "chunks": [{"index": 0, "size": 1024, "nonce": "dummy_nonce_b64"}],
        },
        "commitment_version": "v1",
    }
    r_ver = await async_client.post(f"/api/v1/documents/{doc_id}/versions", headers=headers, json=version_payload)
    assert r_ver.status_code == 201
    ver_data = r_ver.json()
    assert ver_data["document_id"] == doc_id
    assert ver_data["version_number"] == 1
    assert ver_data["status"] == "pending"
    assert ver_data["ciphertext_sha256_hex"] == sha256_dummy
    assert ver_data["object_key"] == f"blobs/{doc_id}/{ver_data['id']}.enc"


@pytest.mark.asyncio
async def test_presigned_upload_url_and_missing_object_failure(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
):
    """Test 2: Presigned upload URL generation and finalization failure when R2 object does not exist."""
    _, headers = await create_user_and_headers(async_client, "owner2@dropsafe.com", "Owner Two")

    # Create document and version intent
    doc = (await async_client.post(
        "/api/v1/documents",
        headers=headers,
        json={"display_name": "secrets.docx"},
    )).json()
    doc_id = doc["id"]

    sha256_dummy = hashlib.sha256(b"payload").hexdigest()
    ver = (await async_client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": 500,
            "ciphertext_sha256_hex": sha256_dummy,
            "manifest": {"chunk_count": 1},
        },
    )).json()
    version_id = ver["id"]

    # Generate presigned upload URL
    r_url = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/upload-url",
        headers=headers,
    )
    assert r_url.status_code == 200
    url_data = r_url.json()
    assert "url" in url_data
    assert url_data["object_key"] == ver["object_key"]

    # Finalize BEFORE uploading ciphertext -> MUST FAIL with 400 STORAGE_OBJECT_NOT_FOUND
    finalize_payload = {
        "wrapped_dek": base64.b64encode(b"dummy_wrapped_dek").decode("ascii"),
        "recipient_encryption_key_id": str(uuid.uuid4()),
    }
    r_final = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/finalize",
        headers=headers,
        json=finalize_payload,
    )
    assert r_final.status_code == 400
    assert r_final.json()["error"]["code"] == "STORAGE_OBJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_successful_finalization_with_signature_and_envelope(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
    db_session: AsyncSession,
):
    """Test 3: Successful finalization when object exists, updating current_version, storing owner key envelope, and audit logs."""
    _, headers = await create_user_and_headers(async_client, "owner3@dropsafe.com", "Owner Three")

    # 1. Register owner's RSA encryption key
    r_enc = await async_client.post(
        "/api/v1/users/me/keys",
        headers=headers,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    assert r_enc.status_code == 201
    enc_key_id = r_enc.json()["id"]

    # 2. Register owner's ECDSA signing key
    ec_priv = ec.generate_private_key(ec.SECP256R1())
    pub_nums = ec_priv.public_key().public_numbers()
    ec_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url_encode(pub_nums.x.to_bytes(32, "big")),
        "y": _b64url_encode(pub_nums.y.to_bytes(32, "big")),
    }
    r_sig = await async_client.post(
        "/api/v1/users/me/keys",
        headers=headers,
        json={
            "key_purpose": "signing",
            "algorithm": "ECDSA-P256",
            "public_key_jwk": ec_jwk,
        },
    )
    assert r_sig.status_code == 201
    sig_key_id = r_sig.json()["id"]

    # 3. Create document and version
    doc = (await async_client.post(
        "/api/v1/documents",
        headers=headers,
        json={"display_name": "contract.pdf"},
    )).json()
    doc_id = doc["id"]

    ciphertext_bytes = b"encrypted_aes_gcm_ciphertext_blocks_here"
    ciphertext_hash = hashlib.sha256(ciphertext_bytes).digest()

    ver = (await async_client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": len(ciphertext_bytes),
            "ciphertext_sha256_hex": ciphertext_hash.hex(),
            "manifest": {"chunks": [{"size": len(ciphertext_bytes)}]},
        },
    )).json()
    version_id = ver["id"]
    object_key = ver["object_key"]

    # 4. Upload ciphertext into test storage adapter
    test_storage.put_object_bytes(object_key, ciphertext_bytes)

    # 5. Sign the ciphertext SHA-256 using owner's private key
    sig_der = ec_priv.sign(ciphertext_hash, ec.ECDSA(hashes.SHA256()))

    # 6. Finalize version with wrapped DEK and cryptographic signature
    wrapped_dek_b64 = base64.b64encode(b"rsa_wrapped_aes_dek_32_bytes").decode("ascii")
    finalize_payload = {
        "wrapped_dek": wrapped_dek_b64,
        "recipient_encryption_key_id": enc_key_id,
        "signature_hex": sig_der.hex(),
        "signature_algorithm": "ECDSA-P256",
        "signing_key_id": sig_key_id,
    }
    r_finalize = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/finalize",
        headers=headers,
        json=finalize_payload,
    )
    assert r_finalize.status_code == 200
    final_doc = r_finalize.json()

    # Verify document and version state
    assert final_doc["current_version"] is not None
    assert final_doc["current_version"]["id"] == version_id
    assert final_doc["current_version"]["status"] == "finalized"
    assert final_doc["current_version"]["signature_hex"] == sig_der.hex()
    assert final_doc["current_version"]["signature_algorithm"] == "ECDSA-P256"

    # Verify database state: DocumentKeyEnvelope exists for owner
    env_stmt = select(DocumentKeyEnvelope).where(
        DocumentKeyEnvelope.document_version_id == uuid.UUID(version_id)
    )
    env = (await db_session.execute(env_stmt)).scalar_one_or_none()
    assert env is not None
    assert env.wrapped_key == b"rsa_wrapped_aes_dek_32_bytes"
    assert env.status == "active"

    # Verify audit events
    audit_stmt = (
        select(AuditEvent)
        .where(AuditEvent.document_id == uuid.UUID(doc_id))
        .order_by(AuditEvent.sequence_number.asc())
    )
    events = (await db_session.execute(audit_stmt)).scalars().all()
    event_types = [e.event_type for e in events]
    assert "document.created" in event_types
    assert "document.version.created" in event_types
    assert "document.version.uploaded" in event_types
    assert "document.version.finalized" in event_types


@pytest.mark.asyncio
async def test_document_listing_and_idor_protection(async_client: AsyncClient):
    """Test 4: Document listing and IDOR protection (unauthorized caller cannot access another user's document)."""
    # User A (Alice)
    _, alice_headers = await create_user_and_headers(async_client, "alice.docs@dropsafe.com", "Alice")
    r_alice_doc = await async_client.post(
        "/api/v1/documents",
        headers=alice_headers,
        json={"display_name": "Alice_Confidential.pdf"},
    )
    alice_doc_id = r_alice_doc.json()["id"]

    # User B (Bob)
    _, bob_headers = await create_user_and_headers(async_client, "bob.docs@dropsafe.com", "Bob")

    # Bob attempts to get Alice's document -> IDOR blocked with generic 404
    r_bob_get = await async_client.get(f"/api/v1/documents/{alice_doc_id}", headers=bob_headers)
    assert r_bob_get.status_code == 404
    assert r_bob_get.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    # Bob lists documents -> Alice's document is NOT returned
    r_bob_list = await async_client.get("/api/v1/documents", headers=bob_headers)
    assert r_bob_list.status_code == 200
    bob_docs = r_bob_list.json()
    assert len(bob_docs) == 0

    # Alice lists documents -> Alice's document is returned
    r_alice_list = await async_client.get("/api/v1/documents", headers=alice_headers)
    assert r_alice_list.status_code == 200
    alice_docs = r_alice_list.json()
    assert len(alice_docs) == 1
    assert alice_docs[0]["id"] == alice_doc_id


@pytest.mark.asyncio
async def test_authorized_download_url_and_wrapped_dek_retrieval(
    async_client: AsyncClient,
    test_storage: InMemoryStorageAdapter,
):
    """Test 5: Authorized download URL generation returning presigned GET URL and caller's wrapped DEK envelope."""
    _, headers = await create_user_and_headers(async_client, "downloader@dropsafe.com", "Downloader")

    # Register encryption key
    enc_resp = await async_client.post(
        "/api/v1/users/me/keys",
        headers=headers,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    enc_key_id = enc_resp.json()["id"]

    # Create, upload, and finalize document
    doc = (await async_client.post(
        "/api/v1/documents",
        headers=headers,
        json={"display_name": "download_test.bin"},
    )).json()
    doc_id = doc["id"]

    data = b"raw_ciphertext_blob_for_download"
    data_hash = hashlib.sha256(data).hexdigest()

    ver = (await async_client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": len(data),
            "ciphertext_sha256_hex": data_hash,
            "manifest": {"chunk_size": 1024},
        },
    )).json()
    version_id = ver["id"]

    # Put bytes in storage
    test_storage.put_object_bytes(ver["object_key"], data)

    # Finalize
    wrapped_dek = base64.b64encode(b"unique_wrapped_dek_key_bytes").decode("ascii")
    await async_client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/finalize",
        headers=headers,
        json={
            "wrapped_dek": wrapped_dek,
            "recipient_encryption_key_id": enc_key_id,
        },
    )

    # 1. Owner requests download URL
    r_dl = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url",
        headers=headers,
    )
    assert r_dl.status_code == 200
    dl_data = r_dl.json()
    assert "download_url" in dl_data
    assert dl_data["object_key"] == ver["object_key"]
    assert dl_data["wrapped_dek"] == wrapped_dek
    assert dl_data["wrapping_algorithm"] == "RSA-OAEP-3072"
    assert dl_data["manifest"] == {"chunk_size": 1024}

    # 2. Unauthorized caller receives 404
    _, other_headers = await create_user_and_headers(async_client, "eavesdropper@dropsafe.com")
    r_bad = await async_client.get(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url",
        headers=other_headers,
    )
    assert r_bad.status_code == 404


@pytest.mark.asyncio
async def test_soft_delete_and_download_intent_blocking(async_client: AsyncClient):
    """Test 6: Soft-deletion blocks subsequent metadata queries and download intents."""
    _, headers = await create_user_and_headers(async_client, "delete_owner@dropsafe.com")

    # Create document
    doc = (await async_client.post(
        "/api/v1/documents",
        headers=headers,
        json={"display_name": "to_be_deleted.pdf"},
    )).json()
    doc_id = doc["id"]

    # Delete document
    r_del = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert r_del.status_code == 204

    # Subsequent GET /documents/{id} returns 404
    r_get = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert r_get.status_code == 404

    # Subsequent version creation returns 404
    r_ver = await async_client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers,
        json={
            "key_version": 1,
            "ciphertext_size_bytes": 100,
            "ciphertext_sha256_hex": hashlib.sha256(b"").hexdigest(),
            "manifest": {},
        },
    )
    assert r_ver.status_code == 404
