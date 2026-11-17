import hashlib
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Response, status
from app.core.config import settings
from app.core.logging import get_logger
from app.storage.adapter import get_storage_adapter

logger = get_logger("app.api.v1.storage")
router = APIRouter(prefix="/storage", tags=["Local Storage Relay"])


@router.put(
    "/{bucket_name}/{object_key:path}",
    status_code=status.HTTP_200_OK,
    summary="Direct Ciphertext Storage Upload Relay",
    description="Accepts encrypted ciphertext payload for local/memory storage backend.",
)
async def upload_ciphertext_relay(
    bucket_name: str,
    object_key: str,
    request: Request,
) -> Response:
    """Relays client-encrypted ciphertext stream into the active storage backend."""
    ciphertext = await request.body()
    storage = get_storage_adapter()

    # Store in memory storage adapter
    storage.put_object_bytes(object_key=object_key, data=ciphertext)

    # Persist to disk if STORAGE_LOCAL_ROOT is set
    if settings.STORAGE_LOCAL_ROOT:
        try:
            local_path = Path(settings.STORAGE_LOCAL_ROOT) / object_key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(ciphertext)
        except Exception as e:
            logger.warning(f"Failed to write local backup of ciphertext: {e}")

    etag = hashlib.sha256(ciphertext).hexdigest()
    logger.info(f"Ciphertext relayed successfully: {object_key} ({len(ciphertext)} bytes, SHA-256: {etag[:8]}...)")
    return Response(
        status_code=status.HTTP_200_OK,
        headers={"ETag": f'"{etag}"'},
    )


@router.get(
    "/{bucket_name}/{object_key:path}",
    status_code=status.HTTP_200_OK,
    summary="Direct Ciphertext Storage Download Relay",
    description="Streams encrypted ciphertext payload for client-side zero-knowledge decryption.",
)
async def download_ciphertext_relay(
    bucket_name: str,
    object_key: str,
    disp: Optional[str] = None,
) -> Response:
    """Streams encrypted ciphertext payload for zero-knowledge decryption in browser."""
    storage = get_storage_adapter()
    try:
        data = storage.get_object_bytes(object_key)
    except Exception:
        if settings.STORAGE_LOCAL_ROOT:
            local_path = Path(settings.STORAGE_LOCAL_ROOT) / object_key
            if local_path.exists():
                data = local_path.read_bytes()
                storage.put_object_bytes(object_key=object_key, data=data)
            else:
                return Response(status_code=status.HTTP_404_NOT_FOUND, content=b"Storage object not found")
        else:
            return Response(status_code=status.HTTP_404_NOT_FOUND, content=b"Storage object not found")

    response_headers = {
        "Content-Length": str(len(data)),
        "Access-Control-Allow-Origin": "*",
    }
    if disp:
        response_headers["Content-Disposition"] = disp

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers=response_headers,
    )
