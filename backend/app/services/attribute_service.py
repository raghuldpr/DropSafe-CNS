import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.issuer_crypto import sign_credential_payload
from app.models.attribute import (
    AttributeCredentialSignature,
    AttributeDefinition,
    UserAttribute,
)
from app.models.user import User, UserKey, UserRole
from app.schemas.attribute import (
    AdminUserSummaryResponse,
    AssignUserAttributeRequest,
    AttributeDefinitionResponse,
    CreateAttributeDefinitionRequest,
    CredentialSignatureResponse,
    UpdateAttributeDefinitionRequest,
    UserAttributeResponse,
)


def _format_credential_response(cred: AttributeCredentialSignature) -> CredentialSignatureResponse:
    """Format database model into API response model with base64 signature and hex hash."""
    return CredentialSignatureResponse(
        id=cred.id,
        user_id=cred.user_id,
        credential_version=cred.credential_version,
        payload=cred.payload,
        payload_hash_hex=cred.payload_hash.hex(),
        signature_b64=base64.b64encode(cred.signature).decode("ascii"),
        issuer_key_id=cred.issuer_key_id,
        status=cred.status,
        issued_at=cred.issued_at,
        expires_at=cred.expires_at,
    )


def validate_attribute_value(
    value_type: str,
    allowed_values: Optional[Any],
    val: Any,
) -> None:
    """Strictly validate attribute value against definition's type and allowed values/bounds."""
    if value_type == "string":
        if not isinstance(val, str) or not val.strip():
            raise ValidationException(
                message="Value must be a non-empty string",
                code="INVALID_ATTRIBUTE_VALUE",
            )
        if allowed_values is not None:
            if isinstance(allowed_values, list) and val not in allowed_values:
                raise ValidationException(
                    message=f"Value '{val}' is not in allowed values: {allowed_values}",
                    code="DISALLOWED_ATTRIBUTE_VALUE",
                )

    elif value_type == "boolean":
        if not isinstance(val, bool):
            raise ValidationException(
                message="Value must be a boolean (True or False)",
                code="INVALID_ATTRIBUTE_VALUE",
            )

    elif value_type == "integer":
        if not isinstance(val, int) or isinstance(val, bool):
            raise ValidationException(
                message="Value must be an integer",
                code="INVALID_ATTRIBUTE_VALUE",
            )
        if allowed_values is not None:
            if isinstance(allowed_values, list) and val not in allowed_values:
                raise ValidationException(
                    message=f"Integer value {val} is not in allowed list: {allowed_values}",
                    code="DISALLOWED_ATTRIBUTE_VALUE",
                )
            elif isinstance(allowed_values, dict):
                min_val = allowed_values.get("min")
                max_val = allowed_values.get("max")
                if min_val is not None and val < min_val:
                    raise ValidationException(
                        message=f"Value {val} is less than minimum allowed ({min_val})",
                        code="DISALLOWED_ATTRIBUTE_VALUE",
                    )
                if max_val is not None and val > max_val:
                    raise ValidationException(
                        message=f"Value {val} is greater than maximum allowed ({max_val})",
                        code="DISALLOWED_ATTRIBUTE_VALUE",
                    )

    elif value_type == "string_set":
        if not isinstance(val, list):
            raise ValidationException(
                message="Value for string_set must be a list of unique strings",
                code="INVALID_ATTRIBUTE_VALUE",
            )
        for item in val:
            if not isinstance(item, str) or not item.strip():
                raise ValidationException(
                    message="All elements in string_set must be non-empty strings",
                    code="INVALID_ATTRIBUTE_VALUE",
                )
        if len(val) != len(set(val)):
            raise ValidationException(
                message="string_set contains duplicate elements",
                code="INVALID_ATTRIBUTE_VALUE",
            )
        if allowed_values is not None and isinstance(allowed_values, list):
            disallowed = set(val) - set(allowed_values)
            if disallowed:
                raise ValidationException(
                    message=f"string_set contains disallowed items: {list(disallowed)}",
                    code="DISALLOWED_ATTRIBUTE_VALUE",
                )
    else:
        raise ValidationException(f"Unsupported value_type '{value_type}'")


async def create_attribute_definition(
    db: AsyncSession,
    admin_id: uuid.UUID,
    payload: CreateAttributeDefinitionRequest,
) -> AttributeDefinitionResponse:
    """Create a new attribute definition in the catalog."""
    stmt = select(AttributeDefinition).where(AttributeDefinition.name == payload.name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictException(
            message=f"Attribute definition '{payload.name}' already exists",
            code="ATTRIBUTE_DEFINITION_EXISTS",
        )

    attr = AttributeDefinition(
        name=payload.name,
        value_type=payload.value_type,
        allowed_values=payload.allowed_values,
        description=payload.description,
        is_active=True,
        created_by=admin_id,
    )
    db.add(attr)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="admin.attribute_definition.created",
        outcome="success",
        actor_user_id=admin_id,
        metadata={"attribute_id": str(attr.id), "name": attr.name, "value_type": attr.value_type},
    )
    return AttributeDefinitionResponse.model_validate(attr)


async def update_attribute_definition(
    db: AsyncSession,
    admin_id: uuid.UUID,
    definition_id: uuid.UUID,
    payload: UpdateAttributeDefinitionRequest,
) -> AttributeDefinitionResponse:
    """Update definition metadata, allowed values, or active status."""
    stmt = select(AttributeDefinition).where(AttributeDefinition.id == definition_id)
    attr = (await db.execute(stmt)).scalar_one_or_none()
    if not attr:
        raise NotFoundException(
            message="Attribute definition not found",
            code="ATTRIBUTE_DEFINITION_NOT_FOUND",
        )

    if payload.allowed_values is not None:
        attr.allowed_values = payload.allowed_values
    if payload.description is not None:
        attr.description = payload.description
    if payload.is_active is not None:
        attr.is_active = payload.is_active

    await db.flush()

    await record_audit_event(
        db=db,
        event_type="admin.attribute_definition.updated",
        outcome="success",
        actor_user_id=admin_id,
        metadata={
            "attribute_id": str(attr.id),
            "name": attr.name,
            "is_active": attr.is_active,
        },
    )
    return AttributeDefinitionResponse.model_validate(attr)


async def list_attribute_definitions(
    db: AsyncSession,
    active_only: bool = False,
) -> List[AttributeDefinitionResponse]:
    """List catalog definitions."""
    stmt = select(AttributeDefinition).order_by(AttributeDefinition.name.asc())
    if active_only:
        stmt = stmt.where(AttributeDefinition.is_active.is_(True))
    res = await db.execute(stmt)
    return [AttributeDefinitionResponse.model_validate(a) for a in res.scalars().all()]


async def _resolve_attribute_definition(
    db: AsyncSession,
    attribute_id_or_name: Union[str, uuid.UUID],
) -> AttributeDefinition:
    """Lookup definition by UUID or unique name."""
    if isinstance(attribute_id_or_name, uuid.UUID):
        stmt = select(AttributeDefinition).where(AttributeDefinition.id == attribute_id_or_name)
    else:
        try:
            val_uuid = uuid.UUID(str(attribute_id_or_name))
            stmt = select(AttributeDefinition).where(
                or_(AttributeDefinition.id == val_uuid, AttributeDefinition.name == str(attribute_id_or_name))
            )
        except ValueError:
            stmt = select(AttributeDefinition).where(AttributeDefinition.name == str(attribute_id_or_name))

    attr = (await db.execute(stmt)).scalar_one_or_none()
    if not attr:
        raise NotFoundException(
            message=f"Attribute definition '{attribute_id_or_name}' not found",
            code="ATTRIBUTE_DEFINITION_NOT_FOUND",
        )
    return attr


async def assign_user_attribute(
    db: AsyncSession,
    admin_id: uuid.UUID,
    user_id: uuid.UUID,
    attribute_id_or_name: Union[str, uuid.UUID],
    payload: AssignUserAttributeRequest,
) -> UserAttributeResponse:
    """Assign or update a user attribute and re-sign the user's cryptographic credential."""
    # 1. Verify user exists
    user_stmt = select(User).where(User.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise NotFoundException("Target user account not found", code="USER_NOT_FOUND")

    # 2. Verify definition exists and is active
    attr_def = await _resolve_attribute_definition(db, attribute_id_or_name)
    if not attr_def.is_active:
        raise ValidationException(
            message=f"Attribute definition '{attr_def.name}' is inactive and cannot be assigned",
            code="INACTIVE_ATTRIBUTE_DEFINITION",
        )

    # 3. Strictly validate value
    validate_attribute_value(attr_def.value_type, attr_def.allowed_values, payload.value)

    # 4. Check validity window
    now = datetime.now(timezone.utc)
    if payload.valid_until and payload.valid_until <= now:
        raise ValidationException(
            message="valid_until timestamp must be in the future",
            code="INVALID_VALIDITY_WINDOW",
        )

    # 5. Upsert UserAttribute row
    user_attr_stmt = select(UserAttribute).where(
        UserAttribute.user_id == user_id,
        UserAttribute.attribute_definition_id == attr_def.id,
    )
    user_attr = (await db.execute(user_attr_stmt)).scalar_one_or_none()

    if user_attr:
        user_attr.value = payload.value
        user_attr.assigned_by = admin_id
        user_attr.valid_from = now
        user_attr.valid_until = payload.valid_until
    else:
        user_attr = UserAttribute(
            user_id=user_id,
            attribute_definition_id=attr_def.id,
            value=payload.value,
            assigned_by=admin_id,
            source="admin",
            valid_from=now,
            valid_until=payload.valid_until,
        )
        db.add(user_attr)

    await db.flush()

    # 6. Re-issue and sign updated credential
    await issue_user_credential_signature(db, user_id)

    # 7. Record audit log
    await record_audit_event(
        db=db,
        event_type="admin.user_attribute.assigned",
        outcome="success",
        actor_user_id=admin_id,
        metadata={
            "target_user_id": str(user_id),
            "attribute_name": attr_def.name,
            "value": payload.value,
        },
    )

    return UserAttributeResponse(
        id=user_attr.id,
        user_id=user_attr.user_id,
        attribute_definition_id=user_attr.attribute_definition_id,
        attribute_name=attr_def.name,
        value_type=attr_def.value_type,
        value=user_attr.value,
        assigned_by=user_attr.assigned_by,
        source=user_attr.source,
        valid_from=user_attr.valid_from,
        valid_until=user_attr.valid_until,
        created_at=user_attr.created_at,
    )


async def remove_user_attribute(
    db: AsyncSession,
    admin_id: uuid.UUID,
    user_id: uuid.UUID,
    attribute_id_or_name: Union[str, uuid.UUID],
) -> None:
    """Remove a user's attribute assignment and re-issue the cryptographic credential."""
    attr_def = await _resolve_attribute_definition(db, attribute_id_or_name)

    stmt = select(UserAttribute).where(
        UserAttribute.user_id == user_id,
        UserAttribute.attribute_definition_id == attr_def.id,
    )
    user_attr = (await db.execute(stmt)).scalar_one_or_none()
    if not user_attr:
        raise NotFoundException(
            message=f"Attribute '{attr_def.name}' is not assigned to user",
            code="USER_ATTRIBUTE_NOT_FOUND",
        )

    await db.delete(user_attr)
    await db.flush()

    # Re-issue credential signature to reflect removed attribute
    await issue_user_credential_signature(db, user_id)

    await record_audit_event(
        db=db,
        event_type="admin.user_attribute.removed",
        outcome="success",
        actor_user_id=admin_id,
        metadata={"target_user_id": str(user_id), "attribute_name": attr_def.name},
    )


async def issue_user_credential_signature(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> AttributeCredentialSignature:
    """Build canonical credential payload binding user identity, active public keys, and attributes, and sign with ECDSA P-256."""
    now = datetime.now(timezone.utc)

    # 1. Fetch user's active keys
    keys_stmt = select(UserKey).where(
        UserKey.user_id == user_id,
        UserKey.status == "active",
    )
    active_keys_list = (await db.execute(keys_stmt)).scalars().all()
    active_keys_dict: Dict[str, Any] = {}
    for k in active_keys_list:
        active_keys_dict[k.key_purpose] = {
            "key_id": str(k.id),
            "algorithm": k.algorithm,
            "fingerprint_hex": k.public_key_fingerprint.hex(),
            "key_version": k.key_version,
        }

    # 2. Fetch user's valid attributes joined with definition
    attrs_stmt = (
        select(UserAttribute, AttributeDefinition)
        .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
        .where(
            UserAttribute.user_id == user_id,
            AttributeDefinition.is_active.is_(True),
            UserAttribute.valid_from <= now,
            or_(UserAttribute.valid_until.is_(None), UserAttribute.valid_until > now),
        )
        .order_by(AttributeDefinition.name.asc())
    )
    attr_results = (await db.execute(attrs_stmt)).all()
    attributes_dict: Dict[str, Any] = {}
    for user_attr, defn in attr_results:
        attributes_dict[defn.name] = {
            "value": user_attr.value,
            "valid_from": user_attr.valid_from.isoformat(),
            "valid_until": user_attr.valid_until.isoformat() if user_attr.valid_until else None,
        }

    # 3. Determine next credential version
    ver_stmt = select(func.coalesce(func.max(AttributeCredentialSignature.credential_version), 0)).where(
        AttributeCredentialSignature.user_id == user_id
    )
    next_ver = (await db.execute(ver_stmt)).scalar_one() + 1

    # 4. Mark prior active credentials as 'superseded'
    await db.execute(
        update(AttributeCredentialSignature)
        .where(
            AttributeCredentialSignature.user_id == user_id,
            AttributeCredentialSignature.status == "active",
        )
        .values(status="superseded")
    )

    # 5. Build canonical credential binding payload
    payload = {
        "schema_version": "v1",
        "user_id": str(user_id),
        "credential_version": next_ver,
        "issuer_key_id": settings.ATTRIBUTE_ISSUER_KEY_ID,
        "issued_at": now.isoformat(),
        "expires_at": None,
        "active_keys": active_keys_dict,
        "attributes": attributes_dict,
    }

    # 6. Sign canonical bytes with ECDSA P-256
    payload_hash, sig_bytes = sign_credential_payload(payload)

    cred = AttributeCredentialSignature(
        user_id=user_id,
        credential_version=next_ver,
        payload=payload,
        payload_hash=payload_hash,
        signature=sig_bytes,
        issuer_key_id=settings.ATTRIBUTE_ISSUER_KEY_ID,
        status="active",
        issued_at=now,
        expires_at=None,
    )
    db.add(cred)
    await db.flush()

    return cred


async def get_user_attributes_and_credential(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Tuple[List[UserAttributeResponse], Optional[CredentialSignatureResponse]]:
    """Retrieve all current attributes and latest active signed credential for a user."""
    # 1. Attributes
    stmt = (
        select(UserAttribute, AttributeDefinition)
        .join(AttributeDefinition, UserAttribute.attribute_definition_id == AttributeDefinition.id)
        .where(UserAttribute.user_id == user_id)
        .order_by(AttributeDefinition.name.asc())
    )
    results = (await db.execute(stmt)).all()
    attr_responses = [
        UserAttributeResponse(
            id=ua.id,
            user_id=ua.user_id,
            attribute_definition_id=ua.attribute_definition_id,
            attribute_name=defn.name,
            value_type=defn.value_type,
            value=ua.value,
            assigned_by=ua.assigned_by,
            source=ua.source,
            valid_from=ua.valid_from,
            valid_until=ua.valid_until,
            created_at=ua.created_at,
        )
        for ua, defn in results
    ]

    # 2. Credential
    cred_stmt = (
        select(AttributeCredentialSignature)
        .where(
            AttributeCredentialSignature.user_id == user_id,
            AttributeCredentialSignature.status == "active",
        )
        .order_by(AttributeCredentialSignature.credential_version.desc())
        .limit(1)
    )
    cred = (await db.execute(cred_stmt)).scalar_one_or_none()
    cred_resp = _format_credential_response(cred) if cred else None
    return attr_responses, cred_resp


async def update_user_roles(
    db: AsyncSession,
    admin_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_roles: List[str],
) -> List[str]:
    """Admin endpoint to modify role assignments. Prevents self-demotion."""
    if admin_id == target_user_id and "admin" not in new_roles:
        raise ValidationException(
            message="Administrators cannot revoke their own admin role",
            code="CANNOT_DEMOTE_SELF",
        )

    target_user = (await db.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if not target_user:
        raise NotFoundException("User account not found", code="USER_NOT_FOUND")

    # Clear old roles
    existing_roles = (
        await db.execute(select(UserRole).where(UserRole.user_id == target_user_id))
    ).scalars().all()
    for r in existing_roles:
        await db.delete(r)

    # Insert new roles
    for r in set(new_roles):
        db.add(UserRole(user_id=target_user_id, role=r, assigned_by=admin_id))

    await db.flush()

    await record_audit_event(
        db=db,
        event_type="admin.user_roles.updated",
        outcome="success",
        actor_user_id=admin_id,
        metadata={"target_user_id": str(target_user_id), "new_roles": list(set(new_roles))},
    )
    return list(set(new_roles))


async def get_admin_user_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> AdminUserSummaryResponse:
    """Retrieve comprehensive administrative view of a user."""
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise NotFoundException("User not found", code="USER_NOT_FOUND")

    attributes, cred = await get_user_attributes_and_credential(db, user_id)
    roles = [r.role for r in user.roles]
    return AdminUserSummaryResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=roles,
        attributes=attributes,
        latest_credential=cred,
        created_at=user.created_at,
    )


async def list_admin_users(
    db: AsyncSession,
    query_str: Optional[str] = None,
) -> List[AdminUserSummaryResponse]:
    """List users for admin overview with search query support."""
    stmt = select(User).options(selectinload(User.roles)).order_by(User.created_at.desc())
    if query_str and query_str.strip():
        term = f"%{query_str.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(term), func.lower(User.display_name).like(term)))

    users = (await db.execute(stmt)).scalars().all()
    summaries = []
    for u in users:
        attrs, cred = await get_user_attributes_and_credential(db, u.id)
        summaries.append(
            AdminUserSummaryResponse(
                id=u.id,
                email=u.email,
                display_name=u.display_name,
                status=u.status,
                roles=[r.role for r in u.roles],
                attributes=attrs,
                latest_credential=cred,
                created_at=u.created_at,
            )
        )
    return summaries


async def update_user_status(
    db: AsyncSession,
    admin_id: uuid.UUID,
    user_id: uuid.UUID,
    status_value: str,
) -> AdminUserSummaryResponse:
    """Update user account status ('active' or 'disabled'). Prevents self-disabling."""
    if admin_id == user_id:
        raise ForbiddenException("Admins cannot modify their own account status", code="CANNOT_MODIFY_SELF_STATUS")

    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise NotFoundException("User not found", code="USER_NOT_FOUND")

    old_status = user.status
    user.status = status_value
    now = datetime.now(timezone.utc)
    if status_value == "disabled":
        user.disabled_at = now
    elif status_value == "active":
        user.disabled_at = None

    await db.flush()

    await record_audit_event(
        db=db,
        event_type="admin.user_status.updated",
        outcome="success",
        actor_user_id=admin_id,
        metadata={
            "target_user_id": str(user_id),
            "old_status": old_status,
            "new_status": status_value,
        },
    )

    return await get_admin_user_summary(db, user_id)
