import hashlib
import urllib.parse
from typing import Any, Dict, Optional, Tuple
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import StorageException
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageAdapter:
    """Cloudflare R2 / S3-compatible Encrypted Object Storage Adapter.

    Supports both Cloudflare R2 and local MinIO/S3-compatible emulators.
    Adheres strictly to zero-knowledge storage: only encrypted ciphertext payloads,
    nonces, and authentication tags are handled.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        s3_client: Optional[Any] = None,
    ):
        self.endpoint_url = endpoint_url or settings.R2_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.R2_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.R2_SECRET_ACCESS_KEY
        self.bucket_name = bucket_name or settings.R2_BUCKET_NAME
        self.region = region or settings.R2_REGION
        self._client = s3_client

    @property
    def client(self) -> Any:
        """Lazily initialize and return boto3 S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in: int = 300,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Generate a short-lived presigned PUT URL for direct client-to-storage ciphertext upload.

        Args:
            object_key: Unique storage key path in bucket (e.g. blobs/{uuid}/{sha256}.enc)
            expires_in: URL lifetime in seconds (default: 300s = 5 minutes)
            content_type: MIME type of the payload (default: application/octet-stream)

        Returns:
            Presigned PUT URL string.
        """
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned upload URL for key '{object_key}': {str(e)}")
            raise StorageException(f"Could not generate storage upload URL: {str(e)}")

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 300,
        response_content_disposition: Optional[str] = None,
    ) -> str:
        """Generate a short-lived presigned GET URL for authorized ciphertext retrieval.

        Args:
            object_key: Storage key of the ciphertext in bucket.
            expires_in: URL lifetime in seconds (default: 300s = 5 minutes).
            response_content_disposition: Optional header to control download filename/disposition.

        Returns:
            Presigned GET URL string.
        """
        try:
            params: Dict[str, Any] = {
                "Bucket": self.bucket_name,
                "Key": object_key,
            }
            if response_content_disposition:
                params["ResponseContentDisposition"] = response_content_disposition

            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned download URL for key '{object_key}': {str(e)}")
            raise StorageException(f"Could not generate storage download URL: {str(e)}")

    def verify_object_exists(self, object_key: str) -> Tuple[bool, int, str]:
        """Verify ciphertext existence, size, and ETag/metadata in storage.

        Args:
            object_key: Target object key in bucket.

        Returns:
            Tuple of (exists: bool, size_bytes: int, etag_or_metadata: str).
            If object does not exist, returns (False, 0, "").
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
            size = int(response.get("ContentLength", 0))
            etag = response.get("ETag", "").strip('"')
            return True, size, etag
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            # Handle 404/NoSuchKey/NotFound as object not found
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False, 0, ""
            # Inspect HTTP status code if present
            http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if http_status == 404:
                return False, 0, ""
            logger.error(f"Storage head_object ClientError on key '{object_key}': {str(e)}")
            raise StorageException(f"Storage verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error inspecting storage object '{object_key}': {str(e)}")
            raise StorageException(f"Storage inspection error: {str(e)}")

    def delete_object(self, object_key: str) -> None:
        """Delete an object from storage bucket."""
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
        except Exception as e:
            logger.error(f"Failed to delete object '{object_key}' from storage: {str(e)}")
            raise StorageException(f"Failed to delete storage object: {str(e)}")

    def put_object_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str]:
        """Directly upload ciphertext bytes (useful for tests and small envelopes)."""
        try:
            params: Dict[str, Any] = {
                "Bucket": self.bucket_name,
                "Key": object_key,
                "Body": data,
                "ContentType": content_type,
            }
            if metadata:
                params["Metadata"] = metadata

            response = self.client.put_object(**params)
            etag = response.get("ETag", "").strip('"')
            return len(data), etag
        except Exception as e:
            logger.error(f"Failed to write bytes to storage key '{object_key}': {str(e)}")
            raise StorageException(f"Failed to store object: {str(e)}")

    def get_object_bytes(self, object_key: str) -> bytes:
        """Directly retrieve ciphertext bytes from storage."""
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
            return response["Body"].read()
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code in ("404", "NoSuchKey", "NotFound"):
                raise StorageException(f"Object '{object_key}' not found in storage")
            raise StorageException(f"Failed to retrieve storage object: {str(e)}")
        except Exception as e:
            raise StorageException(f"Failed to read storage object: {str(e)}")

    def ensure_bucket_exists(self) -> None:
        """Idempotently verify or create bucket (for local MinIO emulator setups)."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except Exception as e:
                logger.warning(f"Could not create storage bucket '{self.bucket_name}': {str(e)}")


class InMemoryStorageAdapter(StorageAdapter):
    """In-memory mock storage adapter for isolated, high-speed unit tests.

    Stores ciphertext blobs in memory and provides deterministic mock presigned URLs.
    """

    def __init__(self, bucket_name: str = "test-vault"):
        super().__init__(bucket_name=bucket_name)
        self._storage: Dict[str, bytes] = {}
        self._metadata: Dict[str, Dict[str, str]] = {}

    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in: int = 300,
        content_type: str = "application/octet-stream",
    ) -> str:
        return f"/api/v1/storage/{self.bucket_name}/{object_key}?action=put&expires={expires_in}"

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 300,
        response_content_disposition: Optional[str] = None,
    ) -> str:
        disp = f"&disp={urllib.parse.quote(response_content_disposition)}" if response_content_disposition else ""
        return f"/api/v1/storage/{self.bucket_name}/{object_key}?action=get&expires={expires_in}{disp}"

    def verify_object_exists(self, object_key: str) -> Tuple[bool, int, str]:
        if object_key in self._storage:
            data = self._storage[object_key]
            etag = hashlib.sha256(data).hexdigest()
            return True, len(data), etag
        if settings.STORAGE_LOCAL_ROOT:
            from pathlib import Path
            p = Path(settings.STORAGE_LOCAL_ROOT) / object_key
            if p.exists():
                data = p.read_bytes()
                self._storage[object_key] = data
                etag = hashlib.sha256(data).hexdigest()
                return True, len(data), etag
        return False, 0, ""

    def delete_object(self, object_key: str) -> None:
        self._storage.pop(object_key, None)
        self._metadata.pop(object_key, None)

    def put_object_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str]:
        self._storage[object_key] = data
        if metadata:
            self._metadata[object_key] = metadata
        etag = hashlib.sha256(data).hexdigest()
        return len(data), etag

    def get_object_bytes(self, object_key: str) -> bytes:
        if object_key not in self._storage:
            raise StorageException(f"Object '{object_key}' not found in in-memory storage")
        return self._storage[object_key]

    def ensure_bucket_exists(self) -> None:
        pass

    put_bytes = put_object_bytes


_global_adapter: Optional[StorageAdapter] = None


def get_storage_adapter() -> StorageAdapter:
    """Return active storage adapter instance based on configuration."""
    global _global_adapter
    if _global_adapter is None:
        if settings.STORAGE_BACKEND == "memory" or settings.is_testing:
            _global_adapter = InMemoryStorageAdapter(bucket_name=settings.R2_BUCKET_NAME)
        else:
            _global_adapter = StorageAdapter()
    return _global_adapter


def set_storage_adapter(adapter: Optional[StorageAdapter]) -> None:
    """Override storage adapter (useful for testing fixtures)."""
    global _global_adapter
    _global_adapter = adapter
