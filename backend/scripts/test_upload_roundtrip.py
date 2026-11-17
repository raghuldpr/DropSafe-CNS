import base64
import hashlib
import json
import os
import urllib.request
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE_URL = "http://localhost:5173/api/v1"


def api_request(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        return resp.status, json.loads(content) if content else {}


def run():
    print("[1] Logging in as Alice via Vite proxy...")
    status, login_res = api_request(
        "/auth/login",
        "POST",
        {"email": "alice@dropsafe.local", "password": "AlicePass123!"},
    )
    assert status == 200, f"Login failed: {status}"
    token = login_res["access_token"]
    print("    Alice authenticated successfully.")

    print("[2] Fetching Alice active cryptographic keys...")
    status, keys = api_request("/users/me/keys", "GET", token=token)
    enc_key = next(
        k for k in keys if k["key_purpose"] == "encryption" and k["status"] == "active"
    )
    print(f"    Active encryption key ID: {enc_key['id']}")

    print("[3] Performing client-side AES-256-GCM encryption on test JPEG payload...")
    plaintext = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"DropSafe Secure Payload Sample " * 200
    dek = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(dek)
    iv = os.urandom(12)
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    ciphertext_sha256 = hashlib.sha256(ciphertext).hexdigest()
    ciphertext_len = len(ciphertext)
    print(f"    Original plaintext size: {len(plaintext)} bytes")
    print(f"    Encrypted ciphertext size: {ciphertext_len} bytes")
    print(f"    Ciphertext SHA-256: {ciphertext_sha256}")

    print("[4] Creating document entry via POST /documents...")
    status, doc = api_request(
        "/documents",
        "POST",
        {"display_name": "recovery_verified_photo.jpg", "media_type": "image/jpeg"},
        token=token,
    )
    assert status == 201, f"Create document failed: {status}"
    doc_id = doc["id"]
    print(f"    Document created with ID: {doc_id}")

    print("[5] Creating version intent via POST /documents/{id}/versions...")
    manifest = {
        "algorithm": "AES-256-GCM",
        "iv_base64": base64.b64encode(iv).decode("ascii"),
        "chunk_size": ciphertext_len,
        "total_size": ciphertext_len,
    }
    status, version = api_request(
        f"/documents/{doc_id}/versions",
        "POST",
        {
            "key_version": 1,
            "ciphertext_size_bytes": ciphertext_len,
            "ciphertext_sha256_hex": ciphertext_sha256,
            "manifest": manifest,
        },
        token=token,
    )
    assert status == 201, f"Version intent creation failed: {status}"
    version_id = version["id"]
    print(f"    Version intent created with ID: {version_id}, status: '{version['status']}'")

    print("[6] Requesting presigned storage upload URL...")
    status, upload_info = api_request(
        f"/documents/{doc_id}/versions/{version_id}/upload-url",
        "POST",
        token=token,
    )
    assert status == 200, f"Upload URL request failed: {status}"
    upload_url = upload_info["url"]
    print(f"    Upload URL received: {upload_url}")

    print("[7] PUTting raw encrypted ciphertext to storage relay...")
    put_target = f"http://localhost:5173{upload_url}" if upload_url.startswith("/") else upload_url
    req_put = urllib.request.Request(
        put_target,
        data=ciphertext,
        headers={"Content-Type": "application/octet-stream"},
        method="PUT",
    )
    with urllib.request.urlopen(req_put) as resp:
        assert resp.status == 200, f"PUT failed: {resp.status}"
        etag = resp.headers.get("ETag")
        print(f"    Ciphertext PUT succeeded with status {resp.status}, ETag: {etag}")

    print("[8] Wrapping DEK with Alice RSA-OAEP public key JWK...")
    pub_jwk = enc_key["public_key_jwk"]
    n_bytes = base64.urlsafe_b64decode(pub_jwk["n"] + "==")
    e_bytes = base64.urlsafe_b64decode(pub_jwk["e"] + "==")
    public_key = rsa.RSAPublicNumbers(
        int.from_bytes(e_bytes, "big"),
        int.from_bytes(n_bytes, "big"),
    ).public_key()
    wrapped_dek = public_key.encrypt(
        dek,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    wrapped_dek_b64 = base64.b64encode(wrapped_dek).decode("ascii")
    print("    DEK wrapped successfully.")

    print("[9] Finalizing version via POST /documents/{id}/versions/{id}/finalize...")
    status, final_doc = api_request(
        f"/documents/{doc_id}/versions/{version_id}/finalize",
        "POST",
        {
            "wrapped_dek": wrapped_dek_b64,
            "recipient_encryption_key_id": enc_key["id"],
        },
        token=token,
    )
    assert status == 200, f"Finalize failed: {status}"
    final_status = final_doc["current_version"]["status"]
    print(f"    Version finalized successfully! Current status: '{final_status}'")
    assert final_status == "finalized", f"Expected version status 'finalized', got '{final_status}'"
    assert final_doc["status"] == "active", f"Expected document status 'active', got '{final_doc['status']}'"

    print("[10] Testing download & decryption roundtrip...")
    status, dl_info = api_request(
        f"/documents/{doc_id}/versions/{version_id}/download-url",
        "GET",
        token=token,
    )
    assert status == 200, f"Download URL failed: {status}"
    dl_url = dl_info["download_url"]
    dl_target = f"http://localhost:5173{dl_url}" if dl_url.startswith("/") else dl_url
    req_dl = urllib.request.Request(dl_target, method="GET")
    with urllib.request.urlopen(req_dl) as resp:
        downloaded_bytes = resp.read()
    assert downloaded_bytes == ciphertext, "Downloaded ciphertext does not match original ciphertext!"
    print(f"    Downloaded {len(downloaded_bytes)} bytes of ciphertext. Digest match verified.")

    # Decrypt with local DEK to verify roundtrip fidelity
    decrypted_plaintext = aesgcm.decrypt(iv, downloaded_bytes, None)
    assert decrypted_plaintext == plaintext, "Decrypted plaintext does not match original plaintext!"
    print(f"    Plaintext decrypted successfully ({len(decrypted_plaintext)} bytes). EXACT MATCH!")

    print("\n>>> ALL 10 STEPS OF CLIENT-SIDE ENCRYPTION, UPLOAD, STORAGE, FINALIZATION, AND DECRYPTION PASSED! <<<")


if __name__ == "__main__":
    run()
