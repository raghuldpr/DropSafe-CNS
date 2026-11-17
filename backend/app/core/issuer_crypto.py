import base64
import hashlib
import json
from functools import lru_cache
from typing import Any, Dict, Tuple
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import settings

# NIST P-256 (secp256r1) curve order
_P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _b64url_encode(data: bytes) -> str:
    """Encode binary bytes into base64url string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data_str: str) -> bytes:
    """Decode unpadded base64url string into bytes."""
    rem = len(data_str) % 4
    if rem:
        data_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode("ascii"))


@lru_cache()
def get_issuer_private_key() -> ec.EllipticCurvePrivateKey:
    """Retrieve or deterministically derive the Attribute Authority's P-256 signing key."""
    raw_key = settings.ATTRIBUTE_ISSUER_SIGNING_KEY.strip()
    if raw_key:
        try:
            return serialization.load_pem_private_key(
                raw_key.encode("utf-8"),
                password=None,
            )  # type: ignore
        except Exception:
            pass

    # Deterministic fallback derivation for dev/test environments
    seed = hashlib.sha256(
        f"{settings.JWT_SIGNING_KEY}:attribute-authority-v1".encode("utf-8")
    ).digest()
    private_number = (int.from_bytes(seed, "big") % (_P256_ORDER - 1)) + 1
    return ec.derive_private_key(private_number, ec.SECP256R1())


def get_issuer_public_key() -> ec.EllipticCurvePublicKey:
    """Return public verification key of the Attribute Authority."""
    return get_issuer_private_key().public_key()


def get_issuer_public_jwk() -> Dict[str, Any]:
    """Return Attribute Authority's public key as an RFC 7517 compliant JWK for client verification."""
    pub_key = get_issuer_public_key()
    pub_numbers = pub_key.public_numbers()
    x_bytes = pub_numbers.x.to_bytes(32, "big")
    y_bytes = pub_numbers.y.to_bytes(32, "big")

    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url_encode(x_bytes),
        "y": _b64url_encode(y_bytes),
        "kid": settings.ATTRIBUTE_ISSUER_KEY_ID,
        "use": "sig",
        "alg": "ES256",
    }


def canonicalize_credential_payload(payload: Dict[str, Any]) -> bytes:
    """Serialize payload using deterministic canonical JSON representation."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_credential_payload(payload: Dict[str, Any]) -> Tuple[bytes, bytes]:
    """Sign credential payload using ECDSA P-256 with SHA-256.

    Returns:
        tuple of (payload_hash_32_bytes, signature_der_bytes)
    """
    canonical_bytes = canonicalize_credential_payload(payload)
    payload_hash = hashlib.sha256(canonical_bytes).digest()

    priv_key = get_issuer_private_key()
    signature_bytes = priv_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))
    return payload_hash, signature_bytes


def verify_credential_signature(payload: Dict[str, Any], signature_bytes: bytes) -> bool:
    """Cryptographically verify credential payload against the issuer's public key."""
    canonical_bytes = canonicalize_credential_payload(payload)
    pub_key = get_issuer_public_key()
    try:
        pub_key.verify(signature_bytes, canonical_bytes, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, Exception):
        return False
