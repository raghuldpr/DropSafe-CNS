import base64
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.issuer_crypto import verify_credential_signature
from app.models.attribute import (
    AttributeCredentialSignature,
    AttributeDefinition,
    UserAttribute,
)
from app.models.audit import AuditEvent
from app.models.user import User, UserRole

# Valid RFC 7517 public JWKs for testing key registration
SAMPLE_RSA_ENCRYPTION_JWK = {
    "kty": "RSA",
    "n": (
        "0vx7agoebGcQSuuPiPSXZzxOdBI47TTU483gb455nuUHiOrMr7BiPCs298450NVGJ7U"
        "tfAU9wk3Kwpx36i61VsEWBnLVureaWYRGUGoI5O655V3C8AvApV7DD624NDTQUsCOUz"
        "HYsmFvpFktQtw4SBXFDDAfgDzA5OmA75stbkW8OV7qU7ZPuv3ghdTQtGoZ675kU7g3T"
    ),
    "e": "AQAB",
}

SAMPLE_EC_SIGNING_JWK = {
    "kty": "EC",
    "crv": "P-256",
    "x": "f83OJ3D2xFMTbKEAhqkBKspbqQIleK2DYhU7uhLsVZs",
    "y": "x_daQauIfDp4nfYXdMd9yLmWBaWucWDOHQpEim4NH4q",
}


async def create_user(
    client: AsyncClient,
    email: str,
    password: str = "Password123!",
    display_name: str = "Test User",
) -> dict:
    """Helper to register a user and return the auth response data."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def promote_to_admin(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Helper to grant 'admin' role directly in the database."""
    role = UserRole(user_id=user_id, role="admin")
    db.add(role)
    await db.commit()


@pytest.mark.asyncio
async def test_admin_boundary_and_permissions(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 1: Non-admin calling admin endpoints receives HTTP 403 Forbidden; unauthenticated receives 401."""
    # 1. Unauthenticated request
    r_unauth = await async_client.get("/api/v1/admin/attribute-definitions")
    assert r_unauth.status_code == 401
    assert r_unauth.json()["error"]["code"] == "NOT_AUTHENTICATED"

    # 2. Authenticated non-admin request
    user_data = await create_user(async_client, "regular_user@dropsafe.com")
    token = user_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r_forbidden = await async_client.get(
        "/api/v1/admin/attribute-definitions",
        headers=headers,
    )
    assert r_forbidden.status_code == 403
    data = r_forbidden.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 3. Non-admin attempting to create an attribute definition
    r_post_forbidden = await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=headers,
        json={"name": "department", "value_type": "string"},
    )
    assert r_post_forbidden.status_code == 403
    assert r_post_forbidden.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_admin_create_attribute_definitions(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 2: Admin creates department (string), clearance_level (integer), is_contractor (boolean), and projects (string_set)."""
    admin_data = await create_user(async_client, "admin1@dropsafe.com", display_name="Admin One")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    # 1. String attribute with allowed values
    r_dept = await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=headers,
        json={
            "name": "department",
            "value_type": "string",
            "allowed_values": ["engineering", "legal", "finance", "security"],
            "description": "User organizational department",
        },
    )
    assert r_dept.status_code == 201
    d_dept = r_dept.json()
    assert d_dept["name"] == "department"
    assert d_dept["value_type"] == "string"
    assert d_dept["is_active"] is True
    assert len(d_dept["allowed_values"]) == 4

    # 2. Integer attribute with bounds
    r_clearance = await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=headers,
        json={
            "name": "clearance_level",
            "value_type": "integer",
            "allowed_values": {"min": 1, "max": 5},
            "description": "Security clearance level from 1 to 5",
        },
    )
    assert r_clearance.status_code == 201
    d_clearance = r_clearance.json()
    assert d_clearance["name"] == "clearance_level"
    assert d_clearance["value_type"] == "integer"
    assert d_clearance["allowed_values"] == {"min": 1, "max": 5}

    # 3. Boolean attribute
    r_contractor = await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=headers,
        json={
            "name": "is_contractor",
            "value_type": "boolean",
            "description": "Whether the user is an external contractor",
        },
    )
    assert r_contractor.status_code == 201
    d_contractor = r_contractor.json()
    assert d_contractor["name"] == "is_contractor"
    assert d_contractor["value_type"] == "boolean"

    # 4. String_set attribute with allowed values list
    r_projects = await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=headers,
        json={
            "name": "projects",
            "value_type": "string_set",
            "allowed_values": ["apollo", "gemini", "titan"],
            "description": "Assigned internal project codenames",
        },
    )
    assert r_projects.status_code == 201
    d_projects = r_projects.json()
    assert d_projects["name"] == "projects"
    assert d_projects["value_type"] == "string_set"

    # Verify listing definitions
    r_list = await async_client.get("/api/v1/admin/attribute-definitions", headers=headers)
    assert r_list.status_code == 200
    defs = r_list.json()
    assert len(defs) == 4
    names = {d["name"] for d in defs}
    assert names == {"department", "clearance_level", "is_contractor", "projects"}


@pytest.mark.asyncio
async def test_assign_valid_attributes_and_issue_credential(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 3: Assigning valid attributes creates signed credential with credential_version = 1."""
    admin_data = await create_user(async_client, "admin2@dropsafe.com")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    # Target user
    target_data = await create_user(async_client, "alice@dropsafe.com", display_name="Alice")
    target_id = target_data["user"]["id"]
    target_headers = {"Authorization": f"Bearer {target_data['access_token']}"}

    # Create definitions
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={
            "name": "department",
            "value_type": "string",
            "allowed_values": ["engineering", "security"],
        },
    )
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={
            "name": "clearance_level",
            "value_type": "integer",
            "allowed_values": {"min": 1, "max": 5},
        },
    )

    # Assign department = "engineering"
    r_assign1 = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/department",
        headers=admin_headers,
        json={"value": "engineering"},
    )
    assert r_assign1.status_code == 200
    assert r_assign1.json()["attribute_name"] == "department"
    assert r_assign1.json()["value"] == "engineering"

    # User fetches their attributes and signed credential
    r_my_attrs = await async_client.get("/api/v1/users/me/attributes", headers=target_headers)
    assert r_my_attrs.status_code == 200
    my_attrs_data = r_my_attrs.json()
    assert len(my_attrs_data["attributes"]) == 1
    assert my_attrs_data["attributes"][0]["attribute_name"] == "department"

    cred = my_attrs_data["latest_credential"]
    assert cred is not None
    assert cred["credential_version"] == 1
    assert cred["status"] == "active"
    assert "payload" in cred
    assert cred["payload"]["attributes"]["department"]["value"] == "engineering"
    assert cred["signature_b64"] is not None
    assert cred["payload_hash_hex"] is not None


@pytest.mark.asyncio
async def test_dynamic_type_and_allowed_values_validation(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 4: Disallowed value or wrong type rejected with HTTP 400."""
    admin_data = await create_user(async_client, "admin3@dropsafe.com")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    target_data = await create_user(async_client, "bob@dropsafe.com")
    target_id = target_data["user"]["id"]

    # Create definitions
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={
            "name": "department",
            "value_type": "string",
            "allowed_values": ["engineering", "legal"],
        },
    )
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={
            "name": "clearance_level",
            "value_type": "integer",
            "allowed_values": {"min": 1, "max": 5},
        },
    )
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={"name": "is_contractor", "value_type": "boolean"},
    )
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={
            "name": "projects",
            "value_type": "string_set",
            "allowed_values": ["apollo", "gemini"],
        },
    )

    # 1. Disallowed string value ("marketing" not in ["engineering", "legal"])
    r1 = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/department",
        headers=admin_headers,
        json={"value": "marketing"},
    )
    assert r1.status_code == 400
    assert r1.json()["error"]["code"] == "DISALLOWED_ATTRIBUTE_VALUE"

    # 2. String passed for integer value
    r2 = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/clearance_level",
        headers=admin_headers,
        json={"value": "top_secret"},
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "INVALID_ATTRIBUTE_VALUE"

    # 3. Integer value out of bounds (10 > max 5)
    r3 = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/clearance_level",
        headers=admin_headers,
        json={"value": 10},
    )
    assert r3.status_code == 400
    assert r3.json()["error"]["code"] == "DISALLOWED_ATTRIBUTE_VALUE"

    # 4. String passed for boolean value
    r4 = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/is_contractor",
        headers=admin_headers,
        json={"value": "yes"},
    )
    assert r4.status_code == 400
    assert r4.json()["error"]["code"] == "INVALID_ATTRIBUTE_VALUE"

    # 5. String_set with disallowed item
    r5 = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/projects",
        headers=admin_headers,
        json={"value": ["apollo", "unauthorized_project"]},
    )
    assert r5.status_code == 400
    assert r5.json()["error"]["code"] == "DISALLOWED_ATTRIBUTE_VALUE"


@pytest.mark.asyncio
async def test_inactive_attribute_definition_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 5: Inactive attribute definition cannot be newly assigned (HTTP 400)."""
    admin_data = await create_user(async_client, "admin4@dropsafe.com")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    target_data = await create_user(async_client, "carol@dropsafe.com")
    target_id = target_data["user"]["id"]

    # Create definition
    r_def = await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={"name": "legacy_dept", "value_type": "string"},
    )
    def_id = r_def.json()["id"]

    # Deactivate definition
    r_patch = await async_client.patch(
        f"/api/v1/admin/attribute-definitions/{def_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["is_active"] is False

    # Attempt assignment
    r_assign = await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/legacy_dept",
        headers=admin_headers,
        json={"value": "engineering"},
    )
    assert r_assign.status_code == 400
    assert r_assign.json()["error"]["code"] == "INACTIVE_ATTRIBUTE_DEFINITION"


@pytest.mark.asyncio
async def test_credential_versioning_and_superseding(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 6: Re-assigning or registering a new key increments credential_version and marks prior as 'superseded'."""
    admin_data = await create_user(async_client, "admin5@dropsafe.com")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    target_data = await create_user(async_client, "david@dropsafe.com")
    target_id = target_data["user"]["id"]
    target_headers = {"Authorization": f"Bearer {target_data['access_token']}"}

    # Setup definitions
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={"name": "department", "value_type": "string"},
    )
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={"name": "clearance_level", "value_type": "integer"},
    )

    # 1. First assignment -> version 1
    await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/department",
        headers=admin_headers,
        json={"value": "security"},
    )
    r1 = await async_client.get("/api/v1/users/me/attributes", headers=target_headers)
    assert r1.json()["latest_credential"]["credential_version"] == 1

    # 2. Second assignment -> version 2
    await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/clearance_level",
        headers=admin_headers,
        json={"value": 4},
    )
    r2 = await async_client.get("/api/v1/users/me/attributes", headers=target_headers)
    assert r2.json()["latest_credential"]["credential_version"] == 2

    # 3. User registers a new cryptographic key -> version 3
    key_resp = await async_client.post(
        "/api/v1/users/me/keys",
        headers=target_headers,
        json={
            "key_purpose": "signing",
            "algorithm": "ECDSA-P256",
            "public_key_jwk": SAMPLE_EC_SIGNING_JWK,
        },
    )
    assert key_resp.status_code == 201

    r3 = await async_client.get("/api/v1/users/me/attributes", headers=target_headers)
    cred3 = r3.json()["latest_credential"]
    assert cred3["credential_version"] == 3
    assert "signing" in cred3["payload"]["active_keys"]

    # Verify database: prior versions (1 and 2) are 'superseded' and version 3 is 'active'
    stmt = (
        select(AttributeCredentialSignature)
        .where(AttributeCredentialSignature.user_id == uuid.UUID(target_id))
        .order_by(AttributeCredentialSignature.credential_version.asc())
    )
    creds = (await db_session.execute(stmt)).scalars().all()
    assert len(creds) == 3
    assert creds[0].credential_version == 1 and creds[0].status == "superseded"
    assert creds[1].credential_version == 2 and creds[1].status == "superseded"
    assert creds[2].credential_version == 3 and creds[2].status == "active"


@pytest.mark.asyncio
async def test_cryptographic_signature_verification_and_anti_tampering(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 7: Signature verification against GET /api/v1/users/issuer-public-key succeeds, and tampering fails verification."""
    admin_data = await create_user(async_client, "admin6@dropsafe.com")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    target_data = await create_user(async_client, "eve@dropsafe.com")
    target_id = target_data["user"]["id"]
    target_headers = {"Authorization": f"Bearer {target_data['access_token']}"}

    # Create and assign attribute
    await async_client.post(
        "/api/v1/admin/attribute-definitions",
        headers=admin_headers,
        json={"name": "department", "value_type": "string"},
    )
    await async_client.put(
        f"/api/v1/admin/users/{target_id}/attributes/department",
        headers=admin_headers,
        json={"value": "engineering"},
    )

    # 1. Fetch issuer public key
    r_key = await async_client.get("/api/v1/users/issuer-public-key")
    assert r_key.status_code == 200
    key_data = r_key.json()
    assert "issuer_key_id" in key_data
    assert key_data["public_jwk"]["kty"] == "EC"
    assert key_data["public_jwk"]["crv"] == "P-256"

    # 2. Fetch user's signed credential
    r_attrs = await async_client.get("/api/v1/users/me/attributes", headers=target_headers)
    cred = r_attrs.json()["latest_credential"]
    payload = cred["payload"]
    sig_bytes = base64.b64decode(cred["signature_b64"])

    # 3. Cryptographically verify signature against untampered payload
    is_valid = verify_credential_signature(payload, sig_bytes)
    assert is_valid is True

    # 4. Tamper with payload (escalate attribute or change user_id)
    tampered_payload = dict(payload)
    tampered_payload["attributes"] = dict(payload["attributes"])
    tampered_payload["attributes"]["department"] = {
        "value": "super_admin_security",
        "valid_from": payload["attributes"]["department"]["valid_from"],
        "valid_until": None,
    }

    # Signature must fail verification on tampered payload
    assert verify_credential_signature(tampered_payload, sig_bytes) is False


@pytest.mark.asyncio
async def test_admin_cannot_self_demote(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 8: Administrator cannot remove their own 'admin' role (HTTP 400)."""
    admin_data = await create_user(async_client, "admin7@dropsafe.com")
    admin_id = uuid.UUID(admin_data["user"]["id"])
    await promote_to_admin(db_session, admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    # Other user
    other_data = await create_user(async_client, "other@dropsafe.com")
    other_id = other_data["user"]["id"]

    # 1. Admin attempts to demote self
    r_demote = await async_client.put(
        f"/api/v1/admin/users/{admin_id}/roles",
        headers=admin_headers,
        json={"roles": ["user"]},
    )
    assert r_demote.status_code == 400
    assert r_demote.json()["error"]["code"] == "CANNOT_DEMOTE_SELF"

    # 2. Admin can promote and modify another user's roles
    r_promote = await async_client.put(
        f"/api/v1/admin/users/{other_id}/roles",
        headers=admin_headers,
        json={"roles": ["user", "auditor"]},
    )
    assert r_promote.status_code == 200
    updated_roles = r_promote.json()["roles"]
    assert "user" in updated_roles
    assert "auditor" in updated_roles

    # Verify audit event for role update
    audit_stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.event_type == "admin.user_roles.updated",
            AuditEvent.actor_user_id == admin_id,
        )
    )
    audit_ev = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit_ev is not None
    assert audit_ev.outcome == "success"
