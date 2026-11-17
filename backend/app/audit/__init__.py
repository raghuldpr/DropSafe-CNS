"""DropSafe Blockchain-Anchored Audit Verification System.

Architectural responsibilities:
1. Append-only, hash-chained cryptographic audit event logging (SHA-256).
2. Merkle Tree generation over audit event batches.
3. Blockchain anchor publisher committing Merkle root state hashes to distributed ledger.
4. Independent verification proof generation allowing clients to cryptographically verify
   that log entries have not been altered or deleted retroactively.
"""

from app.audit.service import (
    compute_audit_event_hash,
    record_audit_event,
    sanitize_audit_metadata,
)

__all__ = [
    "record_audit_event",
    "compute_audit_event_hash",
    "sanitize_audit_metadata",
]
