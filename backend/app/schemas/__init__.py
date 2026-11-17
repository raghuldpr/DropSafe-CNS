from app.schemas.attribute import (
    AdminUserSummaryResponse,
    AssignUserAttributeRequest,
    AttributeDefinitionResponse,
    CreateAttributeDefinitionRequest,
    CredentialSignatureResponse,
    IssuerPublicKeyResponse,
    UpdateAttributeDefinitionRequest,
    UpdateUserRoleRequest,
    UpdateUserRolesResponse,
    UserAttributeResponse,
    UserAttributesWithCredentialResponse,
)
from app.schemas.audit import (
    AuditBatchResponse,
    AuditEventResponse,
    MerkleProofResponse,
    VerifyProofRequest,
    VerifyProofResponse,
)
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    HealthCheckResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
    SuccessResponse,
)
from app.schemas.document import (
    CreateDocumentRequest,
    CreateVersionRequest,
    DocumentResponse,
    DocumentVersionResponse,
    DownloadUrlResponse,
    FinalizeVersionRequest,
    PresignedUrlResponse,
)
from app.schemas.sharing import (
    AccessGrantResponse,
    CreateGrantRequest,
    PolicyResponse,
    PolicyUpdateRequest,
    SharedDocumentResponse,
)
from app.schemas.user import (
    RegisterKeyRequest,
    UpdateProfileRequest,
    UserKeyDirectoryResponse,
    UserKeyResponse,
    UserProfileResponse,
)

__all__ = [
    # Common
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "HealthCheckResponse",
    "MessageResponse",
    "PaginatedResponse",
    "PaginationParams",
    "SuccessResponse",
    # Auth
    "RegisterRequest",
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    # User & Keys
    "UserProfileResponse",
    "UpdateProfileRequest",
    "RegisterKeyRequest",
    "UserKeyResponse",
    "UserKeyDirectoryResponse",
    # Documents
    "CreateDocumentRequest",
    "CreateVersionRequest",
    "FinalizeVersionRequest",
    "DocumentVersionResponse",
    "DocumentResponse",
    "PresignedUrlResponse",
    "DownloadUrlResponse",
    # Sharing
    "PolicyUpdateRequest",
    "PolicyResponse",
    "CreateGrantRequest",
    "AccessGrantResponse",
    "SharedDocumentResponse",
    # Audit & Merkle
    "AuditEventResponse",
    "AuditBatchResponse",
    "MerkleProofResponse",
    "VerifyProofRequest",
    "VerifyProofResponse",
    # Attribute Authority
    "CreateAttributeDefinitionRequest",
    "UpdateAttributeDefinitionRequest",
    "AttributeDefinitionResponse",
    "AssignUserAttributeRequest",
    "UserAttributeResponse",
    "CredentialSignatureResponse",
    "AdminUserSummaryResponse",
    "UpdateUserRoleRequest",
    "UpdateUserRolesResponse",
    "UserAttributesWithCredentialResponse",
    "IssuerPublicKeyResponse",
]
