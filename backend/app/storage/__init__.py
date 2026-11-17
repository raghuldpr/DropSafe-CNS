"""DropSafe Encrypted Blob Storage Layer.

Provides pluggable storage drivers (Cloudflare R2, S3, MinIO, In-Memory) for encrypted file payloads.
The backend operates under zero-knowledge storage principles:
- Only client-side encrypted ciphertexts, nonces, and authentication tags are persisted.
- Plaintext file contents never touch the server disk or memory unencrypted.
"""

from app.storage.adapter import (
    InMemoryStorageAdapter,
    StorageAdapter,
    get_storage_adapter,
    set_storage_adapter,
)

__all__ = [
    "StorageAdapter",
    "InMemoryStorageAdapter",
    "get_storage_adapter",
    "set_storage_adapter",
]
