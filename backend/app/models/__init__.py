"""DropSafe Core Database Models (16 Tables).

Exports all domain models for the DropSafe secure cloud file-sharing platform:
1. User Management & Keys: User, UserRole, UserKey
2. ABAC Attributes & Credentials: AttributeDefinition, UserAttribute, AttributeCredentialSignature
3. Encrypted Documents & Envelopes: Document, DocumentVersion, DocumentKeyEnvelope
4. Access Policies & Grants: AccessPolicy, AccessGrant, ShareLink
5. Audit & Blockchain Anchoring: AuditBatch, AuditEvent, BlockchainAnchor, OutboxJob
"""

from app.db.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.access import AccessGrant, AccessPolicy, ShareLink
from app.models.attribute import (
    AttributeCredentialSignature,
    AttributeDefinition,
    UserAttribute,
)
from app.models.audit import AuditBatch, AuditEvent, BlockchainAnchor, OutboxJob
from app.models.document import Document, DocumentKeyEnvelope, DocumentVersion
from app.models.user import User, UserKey, UserRole

__all__ = [
    # Base and Mixins
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "JSONBType",
    # User Domain (3)
    "User",
    "UserRole",
    "UserKey",
    # ABAC Attribute Domain (3)
    "AttributeDefinition",
    "UserAttribute",
    "AttributeCredentialSignature",
    # Document Domain (3)
    "Document",
    "DocumentVersion",
    "DocumentKeyEnvelope",
    # Access Control Domain (3)
    "AccessPolicy",
    "AccessGrant",
    "ShareLink",
    # Audit & Ledger Domain (4)
    "AuditBatch",
    "AuditEvent",
    "BlockchainAnchor",
    "OutboxJob",
]
