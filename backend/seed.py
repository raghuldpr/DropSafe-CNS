import asyncio
import base64
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Ensure backend directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.attribute import AttributeDefinition, UserAttribute
from app.models.user import User, UserKey, UserRole
from app.schemas.user import RegisterKeyRequest
from app.services.attribute_service import issue_user_credential_signature
from app.services.user_service import register_user_key

logger = get_logger("seed")


def _b64url(data: bytes) -> str:
    """Base64URL encoding without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_demo_rsa_jwk() -> Dict[str, Any]:
    """Generate RFC 7517 compliant RSA-3072 public key JWK for encryption."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public_numbers = private_key.public_key().public_numbers()
    n_bytes = public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")
    e_bytes = public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "n": _b64url(n_bytes),
        "e": _b64url(e_bytes),
    }


def generate_demo_ec_jwk() -> Dict[str, Any]:
    """Generate RFC 7517 compliant ECDSA P-256 public key JWK for signing."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    x_bytes = public_numbers.x.to_bytes(32, "big")
    y_bytes = public_numbers.y.to_bytes(32, "big")
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(x_bytes),
        "y": _b64url(y_bytes),
    }


DEMO_DEFINITIONS = [
    {
        "name": "department",
        "value_type": "string",
        "description": "Employee organizational department or division",
        "allowed_values": ["engineering", "finance", "hr", "legal", "marketing"],
        "is_active": True,
    },
    {
        "name": "clearance_level",
        "value_type": "integer",
        "description": "Security clearance level rating (1 to 5)",
        "allowed_values": None,
        "is_active": True,
    },
    {
        "name": "is_contractor",
        "value_type": "boolean",
        "description": "Indicates if the user is an external contractor",
        "allowed_values": None,
        "is_active": True,
    },
    {
        "name": "project_tags",
        "value_type": "string_set",
        "description": "Active projects or squads the user participates in",
        "allowed_values": None,
        "is_active": True,
    },
]

DEMO_USERS = [
    {
        "email": "admin@dropsafe.local",
        "password": "AdminPass123!",
        "display_name": "System Administrator",
        "roles": ["admin", "user"],
        "attributes": {},
    },
    {
        "email": "alice@dropsafe.local",
        "password": "AlicePass123!",
        "display_name": "Alice Engineer",
        "roles": ["user"],
        "attributes": {
            "department": "engineering",
            "clearance_level": 2,
            "project_tags": ["apollo", "core-infra"],
        },
    },
    {
        "email": "bob@dropsafe.local",
        "password": "BobPass123!",
        "display_name": "Bob Finance",
        "roles": ["user"],
        "attributes": {
            "department": "finance",
            "clearance_level": 1,
            "project_tags": ["audit-q3"],
        },
    },
    {
        "email": "charlie@dropsafe.local",
        "password": "CharliePass123!",
        "display_name": "Charlie Contractor",
        "roles": ["user"],
        "attributes": {
            "department": "engineering",
            "is_contractor": True,
        },
    },
]


async def ensure_admin_user(db: AsyncSession) -> User:
    """Ensure the system admin user exists and return it."""
    admin_data = DEMO_USERS[0]
    email = admin_data["email"]
    stmt = select(User).options(selectinload(User.roles)).where(User.email == email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        pw_hash = hash_password(admin_data["password"])
        user = User(
            email=email,
            display_name=admin_data["display_name"],
            password_hash=pw_hash,
            status="active",
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created demo admin: {email} ({user.id})")
    else:
        user.display_name = admin_data["display_name"]
        user.status = "active"
        user.password_hash = hash_password(admin_data["password"])

    roles_stmt = select(UserRole.role).where(UserRole.user_id == user.id)
    current_roles = set((await db.execute(roles_stmt)).scalars().all())
    for target_role in admin_data["roles"]:
        if target_role not in current_roles:
            new_role = UserRole(user_id=user.id, role=target_role)
            db.add(new_role)

    await db.commit()
    await db.refresh(user)
    return user


async def seed_definitions(db: AsyncSession, admin_id: uuid.UUID) -> Dict[str, AttributeDefinition]:
    """Provision catalog attribute definitions idempotently."""
    defs_by_name = {}
    for d in DEMO_DEFINITIONS:
        stmt = select(AttributeDefinition).where(AttributeDefinition.name == d["name"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.value_type = d["value_type"]
            existing.description = d["description"]
            existing.allowed_values = d["allowed_values"]
            existing.is_active = d["is_active"]
            defs_by_name[d["name"]] = existing
            logger.info(f"Updated attribute definition: '{d['name']}'")
        else:
            new_def = AttributeDefinition(
                name=d["name"],
                value_type=d["value_type"],
                description=d["description"],
                allowed_values=d["allowed_values"],
                is_active=d["is_active"],
                created_by=admin_id,
            )
            db.add(new_def)
            await db.flush()
            defs_by_name[d["name"]] = new_def
            logger.info(f"Created attribute definition: '{d['name']}'")

    await db.commit()
    return defs_by_name


async def seed_users(db: AsyncSession, defs_by_name: Dict[str, AttributeDefinition], admin_id: uuid.UUID) -> None:
    """Seed demo accounts, roles, public cryptographic keys, attributes, and signatures."""
    now = datetime.now(timezone.utc)

    for u_data in DEMO_USERS:
        email = u_data["email"]
        stmt = select(User).options(selectinload(User.roles)).where(User.email == email)
        user = (await db.execute(stmt)).scalar_one_or_none()

        if not user:
            pw_hash = hash_password(u_data["password"])
            user = User(
                email=email,
                display_name=u_data["display_name"],
                password_hash=pw_hash,
                status="active",
            )
            db.add(user)
            await db.flush()
            logger.info(f"Created demo user: {email} ({user.id})")
        else:
            user.display_name = u_data["display_name"]
            user.status = "active"
            user.password_hash = hash_password(u_data["password"])
            logger.info(f"Updated demo user: {email} ({user.id})")

        # Assign Roles
        roles_stmt = select(UserRole.role).where(UserRole.user_id == user.id)
        current_roles = set((await db.execute(roles_stmt)).scalars().all())
        for target_role in u_data["roles"]:
            if target_role not in current_roles:
                new_role = UserRole(user_id=user.id, role=target_role)
                db.add(new_role)
                logger.info(f"Assigned role '{target_role}' to {email}")

        await db.commit()

        # Check and register encryption key if absent
        enc_key_stmt = select(UserKey).where(
            UserKey.user_id == user.id,
            UserKey.key_purpose == "encryption",
            UserKey.status == "active",
        )
        existing_enc_key = (await db.execute(enc_key_stmt)).scalar_one_or_none()
        if not existing_enc_key:
            enc_jwk = generate_demo_rsa_jwk()
            await register_user_key(
                db,
                user.id,
                RegisterKeyRequest(
                    key_purpose="encryption",
                    algorithm="RSA-OAEP-3072",
                    public_key_jwk=enc_jwk,
                ),
            )
            logger.info(f"Registered RSA-OAEP-3072 encryption key for {email}")

        # Check and register signing key if absent
        sig_key_stmt = select(UserKey).where(
            UserKey.user_id == user.id,
            UserKey.key_purpose == "signing",
            UserKey.status == "active",
        )
        existing_sig_key = (await db.execute(sig_key_stmt)).scalar_one_or_none()
        if not existing_sig_key:
            sig_jwk = generate_demo_ec_jwk()
            await register_user_key(
                db,
                user.id,
                RegisterKeyRequest(
                    key_purpose="signing",
                    algorithm="ECDSA-P256",
                    public_key_jwk=sig_jwk,
                ),
            )
            logger.info(f"Registered ECDSA-P256 signing key for {email}")

        # Assign User Attributes
        for attr_name, attr_val in u_data["attributes"].items():
            defn = defs_by_name.get(attr_name)
            if not defn:
                continue

            attr_stmt = select(UserAttribute).where(
                UserAttribute.user_id == user.id,
                UserAttribute.attribute_definition_id == defn.id,
            )
            existing_attr = (await db.execute(attr_stmt)).scalar_one_or_none()
            if existing_attr:
                existing_attr.value = attr_val
                existing_attr.valid_from = now
                existing_attr.valid_until = None
            else:
                new_attr = UserAttribute(
                    user_id=user.id,
                    attribute_definition_id=defn.id,
                    value=attr_val,
                    assigned_by=admin_id,
                    valid_from=now,
                    valid_until=None,
                )
                db.add(new_attr)
            logger.info(f"Set attribute '{attr_name}'={attr_val} for {email}")

        await db.commit()

        # Issue/refresh signed attribute credential signature
        cred = await issue_user_credential_signature(db, user.id)
        await db.commit()
        logger.info(f"Issued credential signature v{cred.credential_version} for {email}")


async def run_seed() -> None:
    """Execute complete database seeding process."""
    logger.info("Starting DropSafe database seeding...")
    async with AsyncSessionLocal() as db:
        admin_user = await ensure_admin_user(db)
        defs_by_name = await seed_definitions(db, admin_user.id)
        await seed_users(db, defs_by_name, admin_user.id)
    logger.info("DropSafe database seeding completed successfully!")


seed_database = run_seed


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_seed())
