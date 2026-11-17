"""DropSafe Attribute-Based Access Control (ABAC) Engine.

Evaluates dynamic authorization decisions combining:
1. Subject Attributes: (User ID, Role, Department, Security Clearance, Group Memberships)
2. Resource Attributes: (File Classification [Public/Internal/Confidential/Restricted], Owner, Expiry, Project Tag)
3. Action Attributes: (view_metadata, download, share, revoke, update_policy, delete)
4. Environment Attributes: (Current Time, Request IP / Subnet, Geolocation, MFA Status)

Enforces strict zero-trust evaluation prior to granting access or decrypting file keys.
"""

from app.policies.evaluator import evaluate_policy
from app.policies.validator import validate_policy_ast

__all__ = ["evaluate_policy", "validate_policy_ast"]
