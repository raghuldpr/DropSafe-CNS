import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    """Immutable, append-only security event record representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence_number: int
    event_type: str
    outcome: str
    actor_user_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    occurred_at: datetime
    event_hash_hex: str
    previous_event_hash_hex: Optional[str] = None
    batch_id: Optional[uuid.UUID] = None
    metadata_payload: Dict[str, Any]


class AuditBatchResponse(BaseModel):
    """Aggregated Merkle tree batch representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_number: int
    first_sequence_number: int
    last_sequence_number: int
    event_count: int
    merkle_root_hex: str
    status: str
    created_at: datetime
    anchored_at: Optional[datetime] = None
    anchors: List[Dict[str, Any]] = []


class MerkleProofResponse(BaseModel):
    """Audit inclusion proof package for offline client verification."""
    model_config = ConfigDict(from_attributes=True)

    batch_id: uuid.UUID
    event_id: uuid.UUID
    event_sequence_number: int
    leaf_hash_hex: str
    merkle_root_hex: str
    proof: List[Dict[str, str]]


class VerifyProofRequest(BaseModel):
    """Payload to cryptographically verify a Merkle audit inclusion proof."""
    model_config = ConfigDict(extra="forbid")

    leaf_hash_hex: str = Field(..., description="Leaf hash hex to verify")
    merkle_root_hex: str = Field(..., description="Expected Merkle root hex")
    proof: List[Dict[str, str]] = Field(..., description="List of proof step dicts with position and hash_hex")


class VerifyProofResponse(BaseModel):
    """Verification result with matched batch and anchor status."""
    is_valid: bool
    matched_batch_id: Optional[uuid.UUID] = None
    anchor_status: Optional[str] = None


class BlockchainAnchorResponse(BaseModel):
    """Immutable blockchain anchor record representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    chain_id: int
    network_name: str
    contract_address: str
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    status: str
    error_code: Optional[str] = None
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    confirmation_count: int = 0
    created_at: datetime
    updated_at: datetime


class VerifyChainResponse(BaseModel):
    """Result of continuous hash-chain sequence integrity validation."""
    chain_valid: bool
    checked_events: int
    first_broken_sequence: Optional[int] = None
