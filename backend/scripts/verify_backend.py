import asyncio
import base64
import hashlib
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure event loop policy for Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Force test configuration
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.issuer_crypto import (
    _b64url_decode,
    _b64url_encode,
    canonicalize_credential_payload,
)
from app.db.base import Base
import app.models  # noqa: F401
from app.db.session import AsyncSessionLocal, engine
from app.main import app as fastapi_app
from app.models.attribute import AttributeCredentialSignature
from app.models.user import User, UserKey, UserRole
from app.storage.adapter import InMemoryStorageAdapter, set_storage_adapter
from app.worker.worker import OutboxWorker
import seed

# Terminal ANSI Color Formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS_TAG = f"{GREEN}[PASS]{RESET}"
FAIL_TAG = f"{RED}[FAIL]{RESET}"
INFO_TAG = f"{BLUE}[INFO]{RESET}"
STAGE_TAG = f"{YELLOW}[STAGE]{RESET}"


class VerificationRunner:
    def __init__(self):
        self.passed_checks = 0
        self.failed_checks = 0
        self.results = []

    def check(self, name: str, condition: bool, details: str = "") -> bool:
        if condition:
            self.passed_checks += 1
            print(f"  {PASS_TAG} {name}")
            self.results.append((name, True, details))
            return True
        else:
            self.failed_checks += 1
            print(f"  {FAIL_TAG} {name} {f'({details})' if details else ''}")
            self.results.append((name, False, details))
            return False


async def run_verification() -> int:
    runner = VerificationRunner()

    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}      DropSafe Backend End-to-End System Smoke Verification           {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    # 0. Initialize Storage and In-Memory Database
    storage_adapter = InMemoryStorageAdapter("verify-vault")
    set_storage_adapter(storage_adapter)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"{INFO_TAG} Test database initialized and InMemoryStorageAdapter attached.\n")

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ---------------------------------------------------------------------
        # STAGE 1: BOOTSTRAP & SEEDING VERIFICATION
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 1: Bootstrap & Demographic Seeding Routine")
        try:
            await seed.seed_database()
            async with AsyncSessionLocal() as db:
                users_stmt = select(User).where(
                    User.email.in_([
                        "admin@dropsafe.local",
                        "alice@dropsafe.local",
                        "bob@dropsafe.local",
                        "charlie@dropsafe.local",
                    ])
                )
                users = (await db.execute(users_stmt)).scalars().all()
                user_map = {u.email: u for u in users}

                runner.check("All 4 demo users seeded into database", len(user_map) == 4)

                admin_u = user_map.get("admin@dropsafe.local")
                alice_u = user_map.get("alice@dropsafe.local")
                bob_u = user_map.get("bob@dropsafe.local")
                charlie_u = user_map.get("charlie@dropsafe.local")

                # Verify roles
                admin_roles_stmt = select(UserRole.role).where(UserRole.user_id == admin_u.id)
                admin_roles = set((await db.execute(admin_roles_stmt)).scalars().all())
                runner.check("Admin has 'admin' and 'user' roles", "admin" in admin_roles and "user" in admin_roles)

                # Verify keys and signed credentials
                all_have_keys = True
                all_have_creds = True
                for u in [admin_u, alice_u, bob_u, charlie_u]:
                    k_stmt = select(UserKey).where(UserKey.user_id == u.id, UserKey.status == "active")
                    keys = (await db.execute(k_stmt)).scalars().all()
                    purposes = {k.key_purpose for k in keys}
                    if not ("encryption" in purposes and "signing" in purposes):
                        all_have_keys = False

                    c_stmt = select(AttributeCredentialSignature).where(
                        AttributeCredentialSignature.user_id == u.id,
                        AttributeCredentialSignature.status == "active",
                    )
                    cred = (await db.execute(c_stmt)).scalar_one_or_none()
                    if not cred or not cred.signature:
                        all_have_creds = False

                runner.check("Active encryption and signing keys registered for all users", all_have_keys)
                runner.check("ECDSA P-256 attribute credential signatures issued for all users", all_have_creds)

        except Exception as e:
            runner.check("Stage 1 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 2: AUTHENTICATION & DUAL SESSION TRANSPORT
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 2: Authentication & Dual-Transport Session (Alice)")
        try:
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "alice@dropsafe.local", "password": "AlicePass123!"},
            )
            runner.check("Alice login returns HTTP 200 OK", login_resp.status_code == 200)
            token_data = login_resp.json()
            alice_token = token_data.get("access_token")
            runner.check("Access token and refresh token returned in JSON body", bool(alice_token and token_data.get("refresh_token")))
            runner.check("HttpOnly access cookie set in response", settings.ACCESS_COOKIE_NAME in login_resp.cookies)

            alice_headers = {"Authorization": f"Bearer {alice_token}"}
            me_resp = await client.get("/api/v1/users/me", headers=alice_headers)
            runner.check("Alice /users/me profile accessible with Bearer token", me_resp.status_code == 200)
            me_json = me_resp.json()
            runner.check("Alice has role 'user'", me_json.get("roles") == ["user"])
        except Exception as e:
            runner.check("Stage 2 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 3: KEY DIRECTORY LOOKUP & CREDENTIAL VERIFICATION
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 3: Public Key Directory Lookup & Attribute Authority Verification")
        try:
            lookup_resp = await client.get("/api/v1/users/lookup?email=bob@dropsafe.local", headers=alice_headers)
            runner.check("Lookup Bob by email returns HTTP 200 OK", lookup_resp.status_code == 200)
            bob_dir = lookup_resp.json()
            bob_enc_keys = [k for k in bob_dir.get("active_keys", []) if k["key_purpose"] == "encryption"]
            runner.check("Bob's RSA-OAEP-3072 encryption key found in directory", len(bob_enc_keys) == 1)
            bob_enc_key_id = bob_enc_keys[0]["id"]

            issuer_resp = await client.get("/api/v1/users/issuer-public-key", headers=alice_headers)
            runner.check("Attribute Authority public key endpoint returns HTTP 200 OK", issuer_resp.status_code == 200)
            issuer_jwk = issuer_resp.json()["public_jwk"]

            # Reconstruct issuer public key and verify Bob's signed credential
            issuer_pub_numbers = ec.EllipticCurvePublicNumbers(
                int.from_bytes(_b64url_decode(issuer_jwk["x"]), "big"),
                int.from_bytes(_b64url_decode(issuer_jwk["y"]), "big"),
                ec.SECP256R1(),
            )
            issuer_pub_key = issuer_pub_numbers.public_key()

            async with AsyncSessionLocal() as db:
                bob_cred = (await db.execute(
                    select(AttributeCredentialSignature).where(
                        AttributeCredentialSignature.user_id == bob_u.id,
                        AttributeCredentialSignature.status == "active",
                    )
                )).scalar_one()

            bob_canonical = canonicalize_credential_payload(bob_cred.payload)
            issuer_pub_key.verify(bob_cred.signature, bob_canonical, ec.ECDSA(hashes.SHA256()))
            runner.check("Bob's Attribute Credential signature verified via Authority public key", True)
        except Exception as e:
            runner.check("Stage 3 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 4: ZERO-KNOWLEDGE UPLOAD & FINALIZATION (ALICE)
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 4: Zero-Knowledge Encrypted Upload & Finalization (Alice)")
        try:
            # Register client signing key
            alice_client_priv = ec.generate_private_key(ec.SECP256R1())
            alice_pub_nums = alice_client_priv.public_key().public_numbers()
            sig_reg = await client.post(
                "/api/v1/users/me/keys",
                headers=alice_headers,
                json={
                    "key_purpose": "signing",
                    "algorithm": "ECDSA-P256",
                    "public_key_jwk": {
                        "kty": "EC",
                        "crv": "P-256",
                        "x": _b64url_encode(alice_pub_nums.x.to_bytes(32, "big")),
                        "y": _b64url_encode(alice_pub_nums.y.to_bytes(32, "big")),
                    },
                },
            )
            alice_signing_key_id = sig_reg.json()["id"]

            async with AsyncSessionLocal() as db:
                alice_enc_key_id = str((await db.execute(
                    select(UserKey.id).where(
                        UserKey.user_id == alice_u.id,
                        UserKey.key_purpose == "encryption",
                        UserKey.status == "active",
                    )
                )).scalar_one())

            # Create document
            doc_res = await client.post(
                "/api/v1/documents",
                headers=alice_headers,
                json={"display_name": "Board_Meeting_Minutes.pdf", "media_type": "application/pdf"},
            )
            runner.check("Alice document created (HTTP 201 Created)", doc_res.status_code == 201)
            doc_id = doc_res.json()["id"]

            # Create version intent
            mock_ciphertext = b"encrypted_aes_256_gcm_ciphertext_sample_bytes_12345"
            ciphertext_hash = hashlib.sha256(mock_ciphertext).digest()
            ver_res = await client.post(
                f"/api/v1/documents/{doc_id}/versions",
                headers=alice_headers,
                json={
                    "key_version": 1,
                    "ciphertext_size_bytes": len(mock_ciphertext),
                    "ciphertext_sha256_hex": ciphertext_hash.hex(),
                    "manifest": {"chunk_size": 65536, "total_chunks": 1},
                },
            )
            runner.check("Version upload intent created (HTTP 201 Created)", ver_res.status_code == 201)
            ver_data = ver_res.json()
            version_id = ver_data["id"]
            object_key = ver_data["object_key"]

            # Request presigned URL and put object directly into storage adapter
            url_res = await client.post(
                f"/api/v1/documents/{doc_id}/versions/{version_id}/upload-url",
                headers=alice_headers,
            )
            runner.check("Presigned upload URL generated (HTTP 200 OK)", url_res.status_code == 200)
            storage_adapter.put_object_bytes(object_key, mock_ciphertext)

            # Finalize version
            alice_sig = alice_client_priv.sign(ciphertext_hash, ec.ECDSA(hashes.SHA256()))
            owner_wrapped_dek = base64.b64encode(b"alice_wrapped_dek_bytes").decode("ascii")
            final_res = await client.post(
                f"/api/v1/documents/{doc_id}/versions/{version_id}/finalize",
                headers=alice_headers,
                json={
                    "wrapped_dek": owner_wrapped_dek,
                    "recipient_encryption_key_id": alice_enc_key_id,
                    "signature_hex": alice_sig.hex(),
                    "signature_algorithm": "ECDSA-P256",
                    "signing_key_id": alice_signing_key_id,
                },
            )
            runner.check("Document version finalized with owner key envelope", final_res.status_code == 200)
            runner.check("Document current_version points to newly finalized version", final_res.json()["current_version"]["id"] == version_id)
        except Exception as e:
            runner.check("Stage 4 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 5: ABAC POLICY ATTACHMENT
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 5: Document ABAC Policy AST Attachment")
        try:
            policy_res = await client.put(
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
            runner.check("ABAC policy AST attached (HTTP 200 OK)", policy_res.status_code == 200)
            runner.check("Policy AST requires department == 'finance'", policy_res.json()["policy_ast"]["value"] == "finance")
        except Exception as e:
            runner.check("Stage 5 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 6: DUAL-LAYER SHARING ENFORCEMENT
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 6: Dual-Layer Sharing Enforcement (Positive & Negative)")
        try:
            # Negative Case: Charlie (department='engineering')
            async with AsyncSessionLocal() as db:
                charlie_enc_key_id = str((await db.execute(
                    select(UserKey.id).where(
                        UserKey.user_id == charlie_u.id,
                        UserKey.key_purpose == "encryption",
                        UserKey.status == "active",
                    )
                )).scalar_one())

            charlie_share_res = await client.post(
                f"/api/v1/documents/{doc_id}/grants",
                headers=alice_headers,
                json={
                    "grantee_user_id": str(charlie_u.id),
                    "permissions": ["read", "download"],
                    "wrapped_dek": base64.b64encode(b"charlie_wrapped_dek").decode("ascii"),
                    "recipient_encryption_key_id": charlie_enc_key_id,
                },
            )
            runner.check("Ineligible recipient Charlie strictly denied (HTTP 403 Forbidden)", charlie_share_res.status_code == 403)
            runner.check("Rejection error code is ABAC_POLICY_DENIED", charlie_share_res.json()["error"]["code"] == "ABAC_POLICY_DENIED")

            # Positive Case: Bob (department='finance')
            bob_wrapped_dek = base64.b64encode(b"bob_wrapped_dek_bytes").decode("ascii")
            bob_share_res = await client.post(
                f"/api/v1/documents/{doc_id}/grants",
                headers=alice_headers,
                json={
                    "grantee_user_id": str(bob_u.id),
                    "permissions": ["read", "download"],
                    "wrapped_dek": bob_wrapped_dek,
                    "recipient_encryption_key_id": bob_enc_key_id,
                },
            )
            runner.check("Eligible recipient Bob granted access (HTTP 201 Created)", bob_share_res.status_code == 201)
            grant_id = bob_share_res.json()["id"]
        except Exception as e:
            runner.check("Stage 6 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 7: AUTHORIZED DOWNLOAD & DEK RETRIEVAL (BOB)
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 7: Authorized Download & Key Envelope Retrieval (Bob)")
        try:
            bob_login = (await client.post(
                "/api/v1/auth/login",
                json={"email": "bob@dropsafe.local", "password": "BobPass123!"},
            )).json()
            bob_headers = {"Authorization": f"Bearer {bob_login['access_token']}"}

            shared_res = await client.get("/api/v1/shared-with-me", headers=bob_headers)
            runner.check("Bob lists shared documents workspace (HTTP 200 OK)", shared_res.status_code == 200)
            runner.check("Alice's document appears in Bob's shared workspace", any(d["document"]["id"] == doc_id for d in shared_res.json()))

            dl_res = await client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url", headers=bob_headers)
            runner.check("Bob receives presigned download URL (HTTP 200 OK)", dl_res.status_code == 200 and "download_url" in dl_res.json())
            runner.check("Bob receives his specific wrapped DEK envelope", dl_res.json().get("wrapped_dek") == bob_wrapped_dek)
        except Exception as e:
            runner.check("Stage 7 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 8: DYNAMIC ATTRIBUTE REVOCATION DEFENSE
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 8: Dynamic Attribute Revocation Defense")
        try:
            admin_login = (await client.post(
                "/api/v1/auth/login",
                json={"email": "admin@dropsafe.local", "password": "AdminPass123!"},
            )).json()
            admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

            admin_reassign = await client.put(
                f"/api/v1/admin/users/{bob_u.id}/attributes/department",
                headers=admin_headers,
                json={"value": "marketing"},
            )
            runner.check("Admin changes Bob's department to 'marketing' (HTTP 200 OK)", admin_reassign.status_code == 200)

            bob_blocked = await client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url", headers=bob_headers)
            runner.check("Bob download immediately blocked after attribute change (HTTP 403 Forbidden)", bob_blocked.status_code == 403)
            runner.check("Blocked reason is ABAC_POLICY_DENIED", bob_blocked.json()["error"]["code"] == "ABAC_POLICY_DENIED")
        except Exception as e:
            runner.check("Stage 8 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 9: OWNER ACCESS REVOCATION DEFENSE
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 9: Owner Grant Revocation Defense")
        try:
            # Revert Bob back to finance
            await client.put(
                f"/api/v1/admin/users/{bob_u.id}/attributes/department",
                headers=admin_headers,
                json={"value": "finance"},
            )

            # Alice revokes Bob's grant
            revoke_res = await client.delete(
                f"/api/v1/documents/{doc_id}/grants/{grant_id}",
                headers=alice_headers,
            )
            runner.check("Alice revokes Bob's grant (HTTP 204 No Content)", revoke_res.status_code == 204)

            # Bob attempts download again
            bob_revoked = await client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/download-url", headers=bob_headers)
            runner.check("Bob download blocked after grant revocation (HTTP 403 Forbidden)", bob_revoked.status_code == 403)
        except Exception as e:
            runner.check("Stage 9 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 10: AUDIT LEDGER, MERKLE PROOF & BLOCKCHAIN ANCHORING
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 10: Append-Only Ledger, Outbox Worker & Merkle Verification")
        try:
            events_res = await client.get("/api/v1/audit-events", headers=admin_headers)
            runner.check("Admin lists audit events ledger (HTTP 200 OK)", events_res.status_code == 200)
            events = events_res.json()
            types = {e["event_type"] for e in events}
            runner.check("Audit trail records auth, document, version, and grant events",
                         all(t in types for t in ["auth.login.success", "document.created", "document.version.finalized", "share.grant.created", "share.grant.revoked"]))

            final_event = next(e for e in events if e["event_type"] == "document.version.finalized")

            # Trigger batch creation
            batch_res = await client.post("/api/v1/audit-batches", headers=admin_headers)
            runner.check("Audit batch created (HTTP 201 Created)", batch_res.status_code == 201)
            batch_id = batch_res.json()["id"]

            # Run outbox worker
            worker = OutboxWorker(worker_id="smoke-worker")
            count = await worker.run_once()
            runner.check("OutboxWorker processed and anchored outbox job", count >= 1)

            # Confirm batch status
            batch_details = (await client.get(f"/api/v1/audit-batches/{batch_id}", headers=admin_headers)).json()
            runner.check("AuditBatch status is 'anchored'", batch_details.get("status") == "anchored")

            # Fetch Merkle proof
            proof_res = await client.get(f"/api/v1/audit-batches/{batch_id}/proofs/{final_event['id']}", headers=admin_headers)
            runner.check("Merkle inclusion proof retrieved (HTTP 200 OK)", proof_res.status_code == 200)
            proof_data = proof_res.json()

            # Verify proof
            verify_valid = await client.post(
                "/api/v1/audit/verify",
                json={
                    "leaf_hash_hex": proof_data["leaf_hash_hex"],
                    "merkle_root_hex": proof_data["merkle_root_hex"],
                    "proof": proof_data["proof"],
                },
            )
            runner.check("Valid Merkle proof verified successfully against batch root", verify_valid.json().get("is_valid") is True)

            # Verify tampered proof fails
            verify_tampered = await client.post(
                "/api/v1/audit/verify",
                json={
                    "leaf_hash_hex": "00" * 32,
                    "merkle_root_hex": proof_data["merkle_root_hex"],
                    "proof": proof_data["proof"],
                },
            )
            runner.check("Tampered Merkle proof rejected by verification endpoint", verify_tampered.json().get("is_valid") is False)
        except Exception as e:
            runner.check("Stage 10 execution", False, str(e))
        print()

        # ---------------------------------------------------------------------
        # STAGE 11: PROTECTED SHARE LINKS & SAFEGUARDS
        # ---------------------------------------------------------------------
        print(f"{STAGE_TAG} Stage 11: Protected Share Links & Safeguards")
        try:
            # 11a. Alice creates protected share link
            raw_share_dek = b"verify_share_link_wrapped_dek"
            wrapped_dek_b64 = base64.b64encode(raw_share_dek).decode("ascii")
            link_res = await client.post(
                f"/api/v1/documents/{doc_id}/share-links",
                headers=alice_headers,
                json={
                    "wrapped_dek": wrapped_dek_b64,
                    "max_uses": 3,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                },
            )
            runner.check("Alice creates zero-knowledge protected share link (HTTP 201 Created)", link_res.status_code == 201)
            token = link_res.json().get("token")
            runner.check("Share link response returns redemption token", bool(token))

            # 11b. Charlie logs in and redeems share link
            charlie_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "charlie@dropsafe.local", "password": "CharliePass123!"},
            )
            charlie_token = charlie_login.json()["access_token"]
            charlie_headers = {"Authorization": f"Bearer {charlie_token}"}

            redeem_res = await client.post(
                "/api/v1/share-links/redeem",
                headers=charlie_headers,
                json={"token": token},
            )
            runner.check("Charlie redeems share link successfully (HTTP 200 OK)", redeem_res.status_code == 200)
            runner.check("Redeemed share link returns wrapped DEK", redeem_res.json().get("wrapped_dek") == wrapped_dek_b64)
            runner.check("Redeemed share link matches document ID", redeem_res.json().get("document", {}).get("id") == doc_id)

            # 11c. Safeguard check: disabled share links returns 403
            try:
                settings.ENABLE_SHARE_LINKS = False
                blocked_res = await client.post(
                    f"/api/v1/documents/{doc_id}/share-links",
                    headers=alice_headers,
                    json={"wrapped_dek": wrapped_dek_b64},
                )
                runner.check("Public share links strictly disabled with HTTP 403 when toggle is False", blocked_res.status_code == 403)
            finally:
                settings.ENABLE_SHARE_LINKS = True
        except Exception as e:
            runner.check("Stage 11 execution", False, str(e))
        print()

    # -------------------------------------------------------------------------
    # FINAL SUMMARY REPORT
    # -------------------------------------------------------------------------
    total = runner.passed_checks + runner.failed_checks
    print(f"{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}Verification Results Summary:{RESET} {runner.passed_checks}/{total} checks passed.")
    if runner.failed_checks == 0:
        print(f"{BOLD}{GREEN}ALL SUBSYSTEM VERIFICATIONS PASSED SUCCESSFULLY! (Status: HEALTHY){RESET}")
        print(f"{BOLD}{CYAN}======================================================================{RESET}\n")
        return 0
    else:
        print(f"{BOLD}{RED}{runner.failed_checks} CHECKS FAILED! (Status: UNHEALTHY){RESET}")
        print(f"{BOLD}{CYAN}======================================================================{RESET}\n")
        return 1


if __name__ == "__main__":
    code = asyncio.run(run_verification())
    sys.exit(code)
