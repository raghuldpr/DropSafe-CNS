import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.attribute import (
    AdminUserSummaryResponse,
    AssignUserAttributeRequest,
    AttributeDefinitionResponse,
    CreateAttributeDefinitionRequest,
    UpdateAttributeDefinitionRequest,
    UpdateUserRoleRequest,
    UpdateUserRolesResponse,
    UpdateUserStatusRequest,
    UserAttributeResponse,
)
from app.services import attribute_service

router = APIRouter(
    prefix="/admin",
    tags=["Admin Attribute Authority"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get(
    "/attribute-definitions",
    response_model=List[AttributeDefinitionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Attribute Definitions",
    description="Lists all ABAC attribute definitions in the catalog.",
)
async def list_attribute_definitions(
    active_only: bool = Query(False, description="Filter for active definitions only"),
    db: AsyncSession = Depends(get_db),
) -> List[AttributeDefinitionResponse]:
    return await attribute_service.list_attribute_definitions(db, active_only=active_only)


@router.post(
    "/attribute-definitions",
    response_model=AttributeDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Attribute Definition",
    description="Registers a new trusted ABAC attribute definition (e.g., department, clearance_level).",
)
async def create_attribute_definition(
    payload: CreateAttributeDefinitionRequest,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttributeDefinitionResponse:
    return await attribute_service.create_attribute_definition(db, current_admin.id, payload)


@router.patch(
    "/attribute-definitions/{definition_id}",
    response_model=AttributeDefinitionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Attribute Definition",
    description="Updates allowed values, description, or active status of an attribute definition.",
)
async def update_attribute_definition(
    definition_id: uuid.UUID,
    payload: UpdateAttributeDefinitionRequest,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttributeDefinitionResponse:
    return await attribute_service.update_attribute_definition(
        db, current_admin.id, definition_id, payload
    )


@router.get(
    "/users",
    response_model=List[AdminUserSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Users for Admin Management",
    description="Lists users with roles, current attributes, and signed credential metadata.",
)
async def list_admin_users(
    q: Optional[str] = Query(None, description="Search term for email or display name"),
    db: AsyncSession = Depends(get_db),
) -> List[AdminUserSummaryResponse]:
    return await attribute_service.list_admin_users(db, query_str=q)


@router.get(
    "/users/{user_id}",
    response_model=AdminUserSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User Admin Summary",
    description="Retrieves a user's account details, role assignments, assigned attributes, and active signed credential.",
)
async def get_admin_user_summary(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AdminUserSummaryResponse:
    return await attribute_service.get_admin_user_summary(db, user_id)


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Status",
    description="Updates user status ('active' or 'disabled'). Prevents an administrator from disabling their own account.",
)
async def update_user_status(
    user_id: uuid.UUID,
    payload: UpdateUserStatusRequest,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserSummaryResponse:
    return await attribute_service.update_user_status(
        db, current_admin.id, user_id, payload.status
    )


@router.put(
    "/users/{user_id}/roles",
    response_model=UpdateUserRolesResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Roles",
    description="Modifies user role assignments. Prevents an administrator from stripping their own admin role.",
)
async def update_user_roles(
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateUserRolesResponse:
    updated_roles = await attribute_service.update_user_roles(
        db, current_admin.id, user_id, payload.roles
    )
    return UpdateUserRolesResponse(user_id=user_id, roles=updated_roles)


@router.put(
    "/users/{user_id}/attributes/{attribute_id}",
    response_model=UserAttributeResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign or Update User Attribute",
    description="Assigns or updates an attribute for a user. Validates type and allowed values, and re-signs the user's credential.",
)
async def assign_user_attribute(
    user_id: uuid.UUID,
    attribute_id: str,
    payload: AssignUserAttributeRequest,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserAttributeResponse:
    return await attribute_service.assign_user_attribute(
        db, current_admin.id, user_id, attribute_id, payload
    )


@router.delete(
    "/users/{user_id}/attributes/{attribute_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove User Attribute",
    description="Removes an assigned attribute from a user and re-signs their cryptographic credential.",
)
async def remove_user_attribute(
    user_id: uuid.UUID,
    attribute_id: str,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await attribute_service.remove_user_attribute(
        db, current_admin.id, user_id, attribute_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
