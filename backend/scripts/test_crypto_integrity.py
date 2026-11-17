import base64
import hashlib
import json
import os
import urllib.request
import urllib.error
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

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

def to_b64(val, length):
    return base64.urlsafe_b64encode(val.to_bytes(length, "big")).decode("ascii").rstrip("=")

def run():
    print("=== TASK 3: CRYPTOGRAPHIC INTEGRITY VERIFICATION ===")

    # 1. Tampered Ciphertext Test
    print("[1] Testing AES-GCM Ciphertext Tamper Resistance...")
    dek = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(dek)
    iv = os.urandom(12)
    original_plaintext = b"Sensitive Medical and Financial Data Block - Top Secret"
    valid_ciphertext = bytearray(aesgcm.encrypt(iv, original_plaintext, None))
    
    # Tamper with 1 byte in middle of ciphertext
    tampered_ciphertext = bytearray(valid_ciphertext)
    tampered_ciphertext[20] ^= 0xFF
    
    tamper_caught = False
    try:
        aesgcm.decrypt(iv, bytes(tampered_ciphertext), None)
    except InvalidTag:
        tamper_caught = True
    assert tamper_caught, "SECURITY FAILURE: AES-GCM failed to catch tampered ciphertext!"
    print("    Tampered ciphertext correctly rejected by AES-GCM authentication tag check (InvalidTag).")

    # 2. Incorrect Key Test
    print("\n[2] Testing Decryption with Incorrect DEK...")
    wrong_dek = AESGCM.generate_key(bit_length=256)
    wrong_aesgcm = AESGCM(wrong_dek)
    wrong_key_caught = False
    try:
        wrong_aesgcm.decrypt(iv, bytes(valid_ciphertext), None)
    except InvalidTag:
        wrong_key_caught = True
    assert wrong_key_caught, "SECURITY FAILURE: Wrong key decrypted ciphertext!"
    print("    Decryption with unauthorized key strictly rejected (InvalidTag).")

    # 3. Authenticate Alice & register RSA encryption and ECDSA signing keys
    print("\n[3] Authenticating Alice and Registering ECDSA-P256 Signing Key...")
    s, r = api_call("/auth/login", "POST", {"email": "alice@dropsafe.local", "password": "AlicePass123!"})
    assert s == 200; token = r["access_token"]; user_id = r["user"]["id"]
    
    # Generate ECDSA key pair
    ec_priv = ec.generate_private_key(ec.SECP256R1())
    ec_pub = ec_priv.public_key().public_numbers()
    ec_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": to_b64(ec_pub.x, 32),
        "y": to_b64(ec_pub.y, 32)
    }
    s, sig_key_resp = api_call("/users/me/keys", "POST", {
        "key_purpose": "signing",
        "algorithm": "ECDSA-P256",
        "public_key_jwk": ec_jwk
    }, token=token)
    assert s in (201, 200); signing_key_id = sig_key_resp["id"]
    print(f"    ECDSA signing key registered (ID: {signing_key_id}).")

    # Get active RSA encryption key
    s, keys = api_call("/users/me/keys", "GET", token=token)
    enc_key = next(k for k in keys if k["key_purpose"] == "encryption" and k["status"] == "active")

    # 4. Create document version
    print("\n[4] Creating new document and version intent...")
    s, doc = api_call("/documents", "POST", {"display_name": "crypto_integrity_check.dat"}, token=token)
    assert s == 201; doc_id = doc["id"]
    
    doc_dek = AESGCM.generate_key(bit_length=256)
    doc_aes = AESGCM(doc_dek)
    doc_iv = os.urandom(12)
    doc_plaintext = b"Payload for cryptographic signature verification"
    doc_ciphertext = doc_aes.encrypt(doc_iv, doc_plaintext, None)
    doc_sha256 = hashlib.sha256(doc_ciphertext).digest()
    doc_sha256_hex = doc_sha256.hex()

    s, ver = api_call(f"/documents/{doc_id}/versions", "POST", {
        "key_version": 1,
        "ciphertext_size_bytes": len(doc_ciphertext),
        "ciphertext_sha256_hex": doc_sha256_hex,
        "manifest": {"iv_b64": base64.b64encode(doc_iv).decode("ascii"), "algo": "AES-256-GCM"}
    }, token=token)
    assert s == 201; ver_id = ver["id"]

    s, up_url_info = api_call(f"/documents/{doc_id}/versions/{ver_id}/upload-url", "POST", token=token)
    up_url = up_url_info["url"]
    put_target = f"http://localhost:5173{up_url}" if up_url.startswith("/") else up_url
    req_put = urllib.request.Request(put_target, data=doc_ciphertext, headers={"Content-Type": "application/octet-stream"}, method="PUT")
    with urllib.request.urlopen(req_put) as resp:
        assert resp.status == 200

    # Wrap DEK for Alice
    pub_jwk = enc_key["public_key_jwk"]
    n_b = base64.urlsafe_b64decode(pub_jwk["n"] + "==")
    e_b = base64.urlsafe_b64decode(pub_jwk["e"] + "==")
    rsa_pub = rsa.RSAPublicNumbers(int.from_bytes(e_b, "big"), int.from_bytes(n_b, "big")).public_key()
    wrapped_dek = base64.b64encode(rsa_pub.encrypt(
        doc_dek,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )).decode("ascii")

    # 5. Sign hash with Alice's ECDSA private key
    valid_signature = ec_priv.sign(doc_sha256, ec.ECDSA(hashes.SHA256()))
    valid_sig_hex = valid_signature.hex()

    # 6. Test Tampered Signature Rejection
    print("\n[5] Testing Tampered Signature Rejection on Finalization...")
    tampered_sig_bytes = bytearray(valid_signature)
    tampered_sig_bytes[10] ^= 0x55
    tampered_sig_hex = tampered_sig_bytes.hex()

    s, err = api_call(f"/documents/{doc_id}/versions/{ver_id}/finalize", "POST", {
        "wrapped_dek": wrapped_dek,
        "recipient_encryption_key_id": enc_key["id"],
        "signature_hex": tampered_sig_hex,
        "signing_key_id": signing_key_id,
        "signature_algorithm": "ECDSA-P256"
    }, token=token)
    print(f"    Tampered signature finalize response -> HTTP {s} (Expected 400/422):", err.get("error", {}).get("message") or err.get("detail"))
    assert s in (400, 422), f"Expected HTTP 400/422 on tampered signature, got {s}"

    # 7. Test Valid Signature Acceptance
    print("\n[6] Testing Valid ECDSA Signature Finalization...")
    s, fin = api_call(f"/documents/{doc_id}/versions/{ver_id}/finalize", "POST", {
        "wrapped_dek": wrapped_dek,
        "recipient_encryption_key_id": enc_key["id"],
        "signature_hex": valid_sig_hex,
        "signing_key_id": signing_key_id,
        "signature_algorithm": "ECDSA-P256"
    }, token=token)
    assert s == 200, f"Expected HTTP 200 on valid signature, got {s}"
    assert fin["current_version"]["signature_hex"] is not None, "Signature hex was not stored on version!"
    print("    Valid ECDSA signature verified and anchored to document version successfully.")

    # 8. Test Private Key Rejection in API schemas
    print("\n[7] Verifying Private Keys are Rejected by API schemas (Zero-Knowledge)...")
    s, err = api_call("/users/me/keys", "POST", {
        "key_purpose": "encryption",
        "algorithm": "RSA-OAEP-3072",
        "public_key_jwk": {
            **pub_jwk,
            "d": "mock_private_exponent_attempting_to_leak_to_backend"
        }
    }, token=token)
    print(f"    Private key 'd' in JWK registration -> HTTP {s} (Expected 400/422):", err.get("error", {}).get("message") or err.get("detail"))
    assert s in (400, 422), f"Schema failed to reject private key material in JWK! HTTP {s}"

    print("\n>>> ALL TASK 3 CRYPTOGRAPHIC INTEGRITY CHECKS PASSED! <<<")

if __name__ == "__main__":
    run()
