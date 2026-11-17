import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationException, ValidationException

# Initialize Argon2id password hasher with secure production parameters
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

# Private key attributes that must NEVER appear in public JWK representations
PRIVATE_JWK_FIELDS = {"d", "p", "q", "dp", "dq", "qi", "oth"}


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, password_hash: Optional[str]) -> bool:
    """Verify plaintext password against an Argon2id hash."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID, roles: List[str]) -> str:
    """Issue a signed JWT access token for authentication and authorization."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Issue a signed JWT refresh token for session extension."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Validate, verify signature, and decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        if payload.get("type") != expected_type:
            raise AuthenticationException(
                message=f"Invalid token type: expected '{expected_type}'",
                code="INVALID_TOKEN_TYPE",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationException(
            message="Token has expired",
            code="TOKEN_EXPIRED",
        )
    except jwt.InvalidTokenError as err:
        raise AuthenticationException(
            message=f"Invalid token: {str(err)}",
            code="INVALID_TOKEN",
        )


def validate_and_fingerprint_public_jwk(
    key_purpose: str,
    algorithm: str,
    jwk_dict: Dict[str, Any],
) -> bytes:
    """Validate public key JWK structure, reject private fields, and compute RFC 7638 SHA-256 fingerprint."""
    if not isinstance(jwk_dict, dict):
        raise ValidationException("Public key JWK must be a valid JSON object")

    # Strictly reject any private key parameters
    if any(field in jwk_dict for field in PRIVATE_JWK_FIELDS):
        raise ValidationException(
            message="JWK contains private key components (d, p, q, dp, dq, qi, oth) which are strictly forbidden in public key registrations",
            code="PRIVATE_KEY_EXPOSURE_PREVENTED",
        )

    if key_purpose == "encryption":
        if algorithm != "RSA-OAEP-3072":
            raise ValidationException(
                f"Unsupported algorithm '{algorithm}' for encryption. Required: 'RSA-OAEP-3072'"
            )
        if jwk_dict.get("kty") != "RSA":
            raise ValidationException("Encryption JWK must have kty='RSA'")
        if "n" not in jwk_dict or "e" not in jwk_dict:
            raise ValidationException("RSA public key JWK must contain 'n' and 'e' parameters")
        canonical = {
            "e": jwk_dict["e"],
            "kty": "RSA",
            "n": jwk_dict["n"],
        }
    elif key_purpose == "signing":
        if algorithm != "ECDSA-P256":
            raise ValidationException(
                f"Unsupported algorithm '{algorithm}' for signing. Required: 'ECDSA-P256'"
            )
        if jwk_dict.get("kty") != "EC":
            raise ValidationException("Signing JWK must have kty='EC'")
        if jwk_dict.get("crv") != "P-256":
            raise ValidationException("Signing JWK must have crv='P-256'")
        if "x" not in jwk_dict or "y" not in jwk_dict:
            raise ValidationException("EC public key JWK must contain 'x' and 'y' coordinates")
        canonical = {
            "crv": "P-256",
            "kty": "EC",
            "x": jwk_dict["x"],
            "y": jwk_dict["y"],
        }
    else:
        raise ValidationException(
            f"Unsupported key_purpose '{key_purpose}'. Must be 'encryption' or 'signing'"
        )

    # Compute deterministic SHA-256 digest over canonical RFC 7638 JSON representation
    canonical_json = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical_json).digest()


def _b64url_decode(data_str: str) -> bytes:
    rem = len(data_str) % 4
    if rem:
        data_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode("ascii"))


def load_ec_public_key_from_jwk(jwk_dict: Dict[str, Any]) -> ec.EllipticCurvePublicKey:
    """Load ECDSA P-256 public key from JWK coordinates."""
    x_bytes = _b64url_decode(jwk_dict["x"])
    y_bytes = _b64url_decode(jwk_dict["y"])
    x_int = int.from_bytes(x_bytes, "big")
    y_int = int.from_bytes(y_bytes, "big")
    return ec.EllipticCurvePublicNumbers(x_int, y_int, ec.SECP256R1()).public_key()


def verify_user_signature(
    public_key_jwk: Dict[str, Any],
    signature_bytes: bytes,
    data_bytes: bytes,
) -> bool:
    """Verify an ECDSA-P256 signature against data bytes using the user's public JWK."""
    try:
        pub_key = load_ec_public_key_from_jwk(public_key_jwk)
        # Try standard SHA256 verification
        try:
            pub_key.verify(signature_bytes, data_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            pass

        # If data_bytes is already a 32-byte hash, try Prehashed
        if len(data_bytes) == 32:
            try:
                pub_key.verify(signature_bytes, data_bytes, ec.ECDSA(Prehashed(hashes.SHA256())))
                return True
            except Exception:
                pass

        return False
    except Exception:
        return False
