import base64
import hashlib
import json
import os
import urllib.request
import urllib.error
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

BASE_URL = "http://localhost:5173/api/v1"

def api_call(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8")
        try:
            err_json = json.loads(body)
        except Exception:
            err_json = {"raw": body}
        return err.code, err_json

def get_or_register_key(token, user_name):
    status, keys = api_call("/users/me/keys", "GET", token=token)
    enc_keys = [k for k in keys if k.get("key_purpose") == "encryption" and k.get("status") == "active"]
    if enc_keys:
        return enc_keys[0]
    
    # Generate and register a test RSA-OAEP key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pub = private_key.public_key()
    pub_nums = pub.public_numbers()
    def to_b64(val, length):
        return base64.urlsafe_b64encode(val.to_bytes(length, "big")).decode("ascii").rstrip("=")
    jwk = {
        "kty": "RSA",
        "n": to_b64(pub_nums.n, 384),
        "e": to_b64(pub_nums.e, 3)
    }
    status, new_key = api_call("/users/me/keys", "POST", {
        "key_purpose": "encryption",
        "algorithm": "RSA-OAEP-3072",
        "public_key_jwk": jwk
    }, token=token)
    assert status == 201, f"Failed registering key for {user_name}: {status}"
    return new_key

def wrap_dek_for_jwk(dek, pub_jwk):
    n_bytes = base64.urlsafe_b64decode(pub_jwk["n"] + "==")
    e_bytes = base64.urlsafe_b64decode(pub_jwk["e"] + "==")
    public_key = rsa.RSAPublicNumbers(
        int.from_bytes(e_bytes, "big"),
        int.from_bytes(n_bytes, "big")
    ).public_key()
    wrapped = public_key.encrypt(
        dek,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(wrapped).decode("ascii")

def run():
    print("=== TASK 2: SHARING AND ABAC VERIFICATION ===")
    
    # 1. Log in users
    print("[1] Authenticating Alice (Owner), Bob (Finance), and Charlie (Contractor)...")
    s, r = api_call("/auth/login", "POST", {"email": "alice@dropsafe.local", "password": "AlicePass123!"})
    assert s == 200; alice_token = r["access_token"]; alice_id = r["user"]["id"]
    
    s, r = api_call("/auth/login", "POST", {"email": "bob@dropsafe.local", "password": "BobPass123!"})
    assert s == 200; bob_token = r["access_token"]; bob_id = r["user"]["id"]
    
    s, r = api_call("/auth/login", "POST", {"email": "charlie@dropsafe.local", "password": "CharliePass123!"})
    assert s == 200; charlie_token = r["access_token"]; charlie_id = r["user"]["id"]
    print("    Alice, Bob, and Charlie authenticated successfully.")
    
    # Ensure keys
    alice_key = get_or_register_key(alice_token, "Alice")
    bob_key = get_or_register_key(bob_token, "Bob")
    charlie_key = get_or_register_key(charlie_token, "Charlie")
    
    # 2. Alice creates and finalizes a document
    print("\n[2] Alice uploads and finalizes a confidential document...")
    s, doc = api_call("/documents", "POST", {"display_name": "q3_financial_projection.pdf", "media_type": "application/pdf"}, token=alice_token)
    assert s == 201; doc_id = doc["id"]
    
    dek = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(dek)
    iv = os.urandom(12)
    plaintext = b"CONFIDENTIAL FINANCIAL RECORD DATA FOR Q3"
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    sha256 = hashlib.sha256(ciphertext).hexdigest()
    
    s, ver = api_call(f"/documents/{doc_id}/versions", "POST", {
        "key_version": 1,
        "ciphertext_size_bytes": len(ciphertext),
        "ciphertext_sha256_hex": sha256,
        "manifest": {"iv_b64": base64.b64encode(iv).decode("ascii"), "algo": "AES-256-GCM"}
    }, token=alice_token)
    assert s == 201; ver_id = ver["id"]
    
    s, up_url_info = api_call(f"/documents/{doc_id}/versions/{ver_id}/upload-url", "POST", token=alice_token)
    assert s == 200
    up_url = up_url_info["url"]
    put_target = f"http://localhost:5173{up_url}" if up_url.startswith("/") else up_url
    req_put = urllib.request.Request(put_target, data=ciphertext, headers={"Content-Type": "application/octet-stream"}, method="PUT")
    with urllib.request.urlopen(req_put) as resp:
        assert resp.status == 200
        
    wrapped_alice = wrap_dek_for_jwk(dek, alice_key["public_key_jwk"])
    s, fin_doc = api_call(f"/documents/{doc_id}/versions/{ver_id}/finalize", "POST", {
        "wrapped_dek": wrapped_alice,
        "recipient_encryption_key_id": alice_key["id"]
    }, token=alice_token)
    assert s == 200
    print(f"    Document created (ID: {doc_id}, Version: {ver_id}) and finalized.")

    # 3. Check IDOR protection for unauthorized users
    print("\n[3] Testing IDOR Protections (Bob and Charlie attempting unauthorized access)...")
    s, err = api_call(f"/documents/{doc_id}", "GET", token=bob_token)
    print(f"    Bob GET /documents/{doc_id} -> HTTP {s} (Expected 404/403):", err.get("error", {}).get("message") or err.get("detail"))
    assert s in (403, 404), f"IDOR Vulnerability: Bob accessed Alice document metadata! HTTP {s}"
    
    s, err = api_call(f"/documents/{doc_id}/versions/{ver_id}/download-url", "GET", token=bob_token)
    print(f"    Bob GET download-url -> HTTP {s} (Expected 404/403):", err.get("error", {}).get("message") or err.get("detail"))
    assert s in (403, 404), f"IDOR Vulnerability: Bob got download URL without grant! HTTP {s}"

    s, err = api_call(f"/documents/{doc_id}", "DELETE", token=bob_token)
    print(f"    Bob DELETE /documents/{doc_id} -> HTTP {s} (Expected 403/404):", err.get("error", {}).get("message") or err.get("detail"))
    assert s in (403, 404), f"IDOR Vulnerability: Bob deleted Alice document! HTTP {s}"

    # 4. Attach ABAC Policy requiring department == 'finance'
    print("\n[4] Alice attaches ABAC Policy requiring department == 'finance'...")
    policy_ast = {
        "op": "eq",
        "attribute": "department",
        "value": "finance"
    }
    s, pol = api_call(f"/documents/{doc_id}/policy", "PUT", {
        "policy_ast": policy_ast,
        "policy_schema_version": "v1"
    }, token=alice_token)
    assert s == 200, f"Attach policy failed: {s} {pol}"
    print(f"    ABAC policy active (ID: {pol['id']}, version: {pol['version_number']}).")

    # 5. Ineligible sharing test (Charlie has department='engineering')
    print("\n[5] Testing policy denial: Alice attempts to share with Charlie (Engineering)...")
    wrapped_charlie = wrap_dek_for_jwk(dek, charlie_key["public_key_jwk"])
    s, err = api_call(f"/documents/{doc_id}/grants", "POST", {
        "grantee_user_id": charlie_id,
        "recipient_encryption_key_id": charlie_key["id"],
        "wrapped_dek": wrapped_charlie,
        "permissions": ["read", "download"]
    }, token=alice_token)
    print(f"    Alice -> Charlie grant creation -> HTTP {s} (Expected 403):", err.get("error", {}).get("message") or err.get("detail"))
    assert s == 403, f"Expected 403 Policy Denial for Charlie, got {s}"

    # 6. Eligible sharing test (Bob has department='finance')
    print("\n[6] Testing policy allowance: Alice shares with Bob (Finance)...")
    wrapped_bob = wrap_dek_for_jwk(dek, bob_key["public_key_jwk"])
    s, grant = api_call(f"/documents/{doc_id}/grants", "POST", {
        "grantee_user_id": bob_id,
        "recipient_encryption_key_id": bob_key["id"],
        "wrapped_dek": wrapped_bob,
        "permissions": ["read", "download"]
    }, token=alice_token)
    assert s == 201, f"Failed granting access to Bob: {s} {grant}"
    grant_id = grant["id"]
    print(f"    Alice -> Bob grant created successfully! Grant ID: {grant_id}")

    # 7. Bob accesses shared file
    print("\n[7] Testing authorized recipient access (Bob)...")
    s, shared_list = api_call("/shared-with-me", "GET", token=bob_token)
    assert s == 200
    found = any(item["document"]["id"] == doc_id for item in shared_list)
    assert found, "Document not found in Bob's shared-with-me list!"
    print("    Bob verifies document is listed in /shared-with-me.")

    s, dl_info = api_call(f"/documents/{doc_id}/versions/{ver_id}/download-url", "GET", token=bob_token)
    assert s == 200, f"Bob failed getting download URL: {s} {dl_info}"
    assert dl_info["wrapped_dek"] == wrapped_bob, "Bob received wrong wrapped DEK!"
    print("    Bob successfully acquired download URL and wrapped DEK envelope.")

    # 8. Revoke grant
    print("\n[8] Alice revokes Bob's access grant...")
    s, _ = api_call(f"/documents/{doc_id}/grants/{grant_id}", "DELETE", token=alice_token)
    assert s == 204, f"Failed revoking grant: {s}"
    print(f"    Grant {grant_id} revoked (HTTP 204).")

    # 9. Verify subsequent protected requests are denied
    print("\n[9] Verifying subsequent access is denied after revocation...")
    s, dl_err = api_call(f"/documents/{doc_id}/versions/{ver_id}/download-url", "GET", token=bob_token)
    print(f"    Bob GET download-url post-revocation -> HTTP {s} (Expected 403/404):", dl_err.get("error", {}).get("message") or dl_err.get("detail"))
    assert s in (403, 404), f"Revocation failed: Bob still has download access! HTTP {s}"

    s, shared_list_after = api_call("/shared-with-me", "GET", token=bob_token)
    assert s == 200
    found_after = any(item["document"]["id"] == doc_id for item in shared_list_after)
    assert not found_after, "Revocation failed: Document still appears in /shared-with-me!"
    print("    Document verified removed from Bob's /shared-with-me list.")

    print("\n>>> ALL TASK 2 SHARING AND ABAC CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run()
