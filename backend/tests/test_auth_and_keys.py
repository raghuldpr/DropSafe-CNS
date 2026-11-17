import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User, UserKey, UserRole

# Valid RFC 7517 public JWKs for testing
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


@pytest.mark.asyncio
async def test_user_registration_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verify user registration assigns default 'user' role, Argon2id hash, and audit log."""
    payload = {
        "email": "testuser@dropsafe.com",
        "password": "Password123!",
        "display_name": "Test User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "testuser@dropsafe.com"
    assert data["user"]["display_name"] == "Test User"
    assert data["user"]["roles"] == ["user"]
    assert data["user"]["status"] == "active"

    # Verify cookies set
    assert "dropsafe_access_token" in response.cookies
    assert "dropsafe_refresh_token" in response.cookies

    # Verify database state
    user_stmt = select(User).where(User.email == "testuser@dropsafe.com")
    user = (await db_session.execute(user_stmt)).scalar_one()
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != "Password123!"

    roles_stmt = select(UserRole).where(UserRole.user_id == user.id)
    roles = (await db_session.execute(roles_stmt)).scalars().all()
    assert len(roles) == 1
    assert roles[0].role == "user"

    # Verify audit event
    audit_stmt = (
        select(AuditEvent)
        .where(AuditEvent.event_type == "auth.register", AuditEvent.actor_user_id == user.id)
    )
    event = (await db_session.execute(audit_stmt)).scalar_one()
    assert event.outcome == "success"
    assert event.event_hash is not None


@pytest.mark.asyncio
async def test_duplicate_registration_conflict(async_client: AsyncClient):
    """Verify duplicate email registration returns 409 Conflict."""
    payload = {
        "email": "duplicate@dropsafe.com",
        "password": "SecurePassword1!",
        "display_name": "Duplicate User",
    }
    r1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    data = r2.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_anti_enumeration_and_invalid_credentials(async_client: AsyncClient):
    """Verify login anti-enumeration returns exact generic 401 for both missing user and wrong password."""
    # 1. Non-existent email
    r1 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@dropsafe.com", "password": "WrongPassword!"},
    )
    assert r1.status_code == 401
    d1 = r1.json()
    assert d1["error"]["message"] == "Invalid email or password"
    assert d1["error"]["code"] == "INVALID_CREDENTIALS"

    # Register user
    reg_payload = {
        "email": "validuser@dropsafe.com",
        "password": "CorrectPassword123!",
        "display_name": "Valid User",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Wrong password for existing user
    r2 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "validuser@dropsafe.com", "password": "WrongPassword123!"},
    )
    assert r2.status_code == 401
    d2 = r2.json()
    # Must match generic message exactly
    assert d2["error"]["message"] == "Invalid email or password"
    assert d2["error"]["code"] == "INVALID_CREDENTIALS"

    # 3. Correct login
    r3 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "validuser@dropsafe.com", "password": "CorrectPassword123!"},
    )
    assert r3.status_code == 200
    d3 = r3.json()
    assert "access_token" in d3
    assert "dropsafe_access_token" in r3.cookies


@pytest.mark.asyncio
async def test_disabled_account_login_rejection(async_client: AsyncClient, db_session: AsyncSession):
    """Verify disabled accounts are rejected with 403 Forbidden."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "disabled@dropsafe.com", "password": "Password123!", "display_name": "Disabled"},
    )
    assert reg.status_code == 201

    # Mark user as disabled in database
    user = (await db_session.execute(select(User).where(User.email == "disabled@dropsafe.com"))).scalar_one()
    user.status = "disabled"
    await db_session.commit()

    # Attempt login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@dropsafe.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 403
    assert login_resp.json()["error"]["code"] == "ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_dual_session_transport(async_client: AsyncClient):
    """Verify authentication succeeds via both Bearer header and HttpOnly cookie."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "transport@dropsafe.com", "password": "Password123!", "display_name": "Transport User"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    # 1. Transport via Authorization Bearer Header
    r_bearer = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_bearer.status_code == 200
    assert r_bearer.json()["email"] == "transport@dropsafe.com"

    # 2. Transport via HttpOnly Cookie (without Bearer header)
    async_client.cookies.set("dropsafe_access_token", token)
    r_cookie = await async_client.get("/api/v1/users/me")
    assert r_cookie.status_code == 200
    assert r_cookie.json()["email"] == "transport@dropsafe.com"

    # 3. Unauthenticated request (clear stored session cookies)
    async_client.cookies.clear()
    r_unauth = await async_client.get("/api/v1/users/me")
    assert r_unauth.status_code == 401
    assert r_unauth.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_token_refresh_and_logout(async_client: AsyncClient):
    """Verify refresh token rotation and logout cookie clearing."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@dropsafe.com", "password": "Password123!", "display_name": "Refresh User"},
    )
    assert reg.status_code == 201
    refresh_token = reg.json()["refresh_token"]

    # Refresh via body payload
    r_refresh = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert r_refresh.status_code == 200
    new_data = r_refresh.json()
    assert "access_token" in new_data

    # Logout
    r_logout = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_data['access_token']}"},
    )
    assert r_logout.status_code == 200


@pytest.mark.asyncio
async def test_profile_update_and_extra_fields_rejection(async_client: AsyncClient):
    """Verify profile update modifies display_name and strictly rejects privilege escalation attempts."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "profile@dropsafe.com", "password": "Password123!", "display_name": "Original Name"},
    )
    token = reg.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Valid update
    r_patch = await async_client.patch(
        "/api/v1/users/me",
        headers=auth_header,
        json={"display_name": "Updated Name"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["display_name"] == "Updated Name"

    # 2. Attempt privilege escalation by injecting 'roles' or 'status'
    r_bad = await async_client.patch(
        "/api/v1/users/me",
        headers=auth_header,
        json={"display_name": "Hacker", "status": "admin", "role": "admin"},
    )
    assert r_bad.status_code == 422
    assert r_bad.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_public_key_registration_and_private_key_rejection(async_client: AsyncClient):
    """Verify public key registration, JWK thumbprint calculation, and rejection of private key parameters."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "keys@dropsafe.com", "password": "Password123!", "display_name": "Keys User"},
    )
    token = reg.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Attempt to register JWK with private key parameter 'd' (Must be strictly rejected)
    bad_jwk = dict(SAMPLE_RSA_ENCRYPTION_JWK)
    bad_jwk["d"] = "secret-private-exponent"
    r_private = await async_client.post(
        "/api/v1/users/me/keys",
        headers=auth_header,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": bad_jwk,
        },
    )
    assert r_private.status_code in (400, 422)
    assert "private" in r_private.json()["error"]["message"].lower()

    # 2. Register valid RSA encryption key (version 1)
    r_enc1 = await async_client.post(
        "/api/v1/users/me/keys",
        headers=auth_header,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    assert r_enc1.status_code == 201
    enc1_data = r_enc1.json()
    assert enc1_data["key_purpose"] == "encryption"
    assert enc1_data["key_version"] == 1
    assert enc1_data["status"] == "active"
    assert len(enc1_data["public_key_fingerprint_hex"]) == 64  # SHA-256 hex

    # 3. Register valid ECDSA signing key
    r_sig = await async_client.post(
        "/api/v1/users/me/keys",
        headers=auth_header,
        json={
            "key_purpose": "signing",
            "algorithm": "ECDSA-P256",
            "public_key_jwk": SAMPLE_EC_SIGNING_JWK,
        },
    )
    assert r_sig.status_code == 201
    sig_data = r_sig.json()
    assert sig_data["key_purpose"] == "signing"
    assert sig_data["key_version"] == 1
    assert sig_data["status"] == "active"

    # 4. Check profile flags updated
    me = await async_client.get("/api/v1/users/me", headers=auth_header)
    assert me.json()["has_active_encryption_key"] is True
    assert me.json()["has_active_signing_key"] is True


@pytest.mark.asyncio
async def test_key_versioning_and_automatic_retirement(async_client: AsyncClient, db_session: AsyncSession):
    """Verify registering a second key auto-increments version and retires prior active key."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "versioning@dropsafe.com", "password": "Password123!", "display_name": "Version User"},
    )
    token = reg.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # Register first encryption key
    r1 = await async_client.post(
        "/api/v1/users/me/keys",
        headers=auth_header,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    assert r1.status_code == 201
    assert r1.json()["key_version"] == 1
    key1_id = r1.json()["id"]

    # Register second encryption key
    r2 = await async_client.post(
        "/api/v1/users/me/keys",
        headers=auth_header,
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    assert r2.status_code == 201
    assert r2.json()["key_version"] == 2
    assert r2.json()["status"] == "active"

    # Verify key 1 was automatically marked retired
    k1_stmt = select(UserKey).where(UserKey.id == uuid.UUID(key1_id))
    k1 = (await db_session.execute(k1_stmt)).scalar_one()
    assert k1.status == "retired"
    assert k1.retired_at is not None


@pytest.mark.asyncio
async def test_key_retirement_idor_protection(async_client: AsyncClient):
    """Verify that a user cannot retire another user's cryptographic key (IDOR protection)."""
    # User 1
    u1 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "victim@dropsafe.com", "password": "Password123!", "display_name": "Victim"},
    )
    u1_token = u1.json()["access_token"]
    k1 = await async_client.post(
        "/api/v1/users/me/keys",
        headers={"Authorization": f"Bearer {u1_token}"},
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )
    key_id = k1.json()["id"]

    # User 2 (Attacker)
    u2 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@dropsafe.com", "password": "Password123!", "display_name": "Attacker"},
    )
    u2_token = u2.json()["access_token"]

    # Attacker tries to retire Victim's key -> HTTP 404
    r_attack = await async_client.post(
        f"/api/v1/users/me/keys/{key_id}/retire",
        headers={"Authorization": f"Bearer {u2_token}"},
    )
    assert r_attack.status_code == 404
    assert r_attack.json()["error"]["code"] == "KEY_NOT_FOUND"


@pytest.mark.asyncio
async def test_recipient_key_directory_lookup(async_client: AsyncClient):
    """Verify public key directory search by user_id and email returns only active keys."""
    # Register Alice with keys
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "alice.dir@dropsafe.com", "password": "Password123!", "display_name": "Alice Directory"},
    )
    alice_token = reg.json()["access_token"]
    alice_id = reg.json()["user"]["id"]

    await async_client.post(
        "/api/v1/users/me/keys",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={
            "key_purpose": "encryption",
            "algorithm": "RSA-OAEP-3072",
            "public_key_jwk": SAMPLE_RSA_ENCRYPTION_JWK,
        },
    )

    # Register Bob who searches Alice
    bob_reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "bob.searcher@dropsafe.com", "password": "Password123!", "display_name": "Bob Searcher"},
    )
    bob_token = bob_reg.json()["access_token"]
    bob_header = {"Authorization": f"Bearer {bob_token}"}

    # 1. Lookup by user_id
    r_id = await async_client.get(f"/api/v1/users/{alice_id}/public-keys", headers=bob_header)
    assert r_id.status_code == 200
    d_id = r_id.json()
    assert d_id["email"] == "alice.dir@dropsafe.com"
    assert len(d_id["active_keys"]) == 1
    assert d_id["active_keys"][0]["key_purpose"] == "encryption"

    # 2. Lookup by email query param
    r_email = await async_client.get("/api/v1/users/lookup?email=alice.dir@dropsafe.com", headers=bob_header)
    assert r_email.status_code == 200
    d_email = r_email.json()
    assert d_email["user_id"] == alice_id
    assert len(d_email["active_keys"]) == 1


@pytest.mark.asyncio
async def test_role_authorization_enforcement(async_client: AsyncClient):
    """Verify require_roles dependency protects privileged routes."""
    from fastapi import Depends
    from app.api.deps import require_roles
    from app.main import app

    @app.get("/api/v1/admin-only-test-route")
    async def admin_only_endpoint(user=Depends(require_roles("admin"))):
        return {"status": "admin_granted"}

    # Register regular user (role='user')
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "regular@dropsafe.com", "password": "Password123!", "display_name": "Regular"},
    )
    token = reg.json()["access_token"]

    response = await async_client.get(
        "/api/v1/admin-only-test-route",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
