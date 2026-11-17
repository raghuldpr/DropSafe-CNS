import io
from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

from app.core.exceptions import StorageException
from app.storage.adapter import (
    InMemoryStorageAdapter,
    StorageAdapter,
    get_storage_adapter,
    set_storage_adapter,
)


def test_boto3_presigned_url_generation_offline():
    """Verify real boto3 S3 client produces valid SigV4 presigned URLs without external network calls."""
    adapter = StorageAdapter(
        endpoint_url="https://fake-r2-account.r2.cloudflarestorage.com",
        access_key_id="test-access-key-id",
        secret_access_key="test-secret-access-key-minimum-chars",
        bucket_name="dropsafe-production-vault",
        region="auto",
    )

    object_key = "blobs/123e4567-e89b-12d3-a456-426614174000/cipher.bin"

    # 1. Presigned PUT (Upload) URL
    upload_url = adapter.generate_presigned_upload_url(object_key, expires_in=600)
    assert upload_url.startswith("https://fake-r2-account.r2.cloudflarestorage.com/dropsafe-production-vault/blobs/")
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in upload_url
    assert "X-Amz-Credential=test-access-key-id" in upload_url
    assert "X-Amz-Signature=" in upload_url
    assert "X-Amz-Expires=600" in upload_url

    # 2. Presigned GET (Download) URL
    download_url = adapter.generate_presigned_download_url(
        object_key,
        expires_in=300,
        response_content_disposition='attachment; filename="encrypted.bin"',
    )
    assert download_url.startswith("https://fake-r2-account.r2.cloudflarestorage.com/dropsafe-production-vault/blobs/")
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in download_url
    assert "X-Amz-Signature=" in download_url
    assert "response-content-disposition=" in download_url


def test_storage_adapter_verify_object_exists_found():
    """Verify verify_object_exists returns (True, size, etag) when head_object succeeds."""
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = {
        "ContentLength": 4096,
        "ETag": '"3a7bd8c9d12345"',
    }

    adapter = StorageAdapter(bucket_name="test-bucket", s3_client=mock_s3)
    exists, size, etag = adapter.verify_object_exists("blobs/test.enc")

    assert exists is True
    assert size == 4096
    assert etag == "3a7bd8c9d12345"
    mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="blobs/test.enc")


def test_storage_adapter_verify_object_exists_not_found():
    """Verify verify_object_exists returns (False, 0, '') when head_object returns 404 NoSuchKey."""
    mock_s3 = MagicMock()
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

    adapter = StorageAdapter(bucket_name="test-bucket", s3_client=mock_s3)
    exists, size, etag = adapter.verify_object_exists("blobs/nonexistent.enc")

    assert exists is False
    assert size == 0
    assert etag == ""


def test_storage_adapter_verify_object_exists_server_error():
    """Verify unexpected ClientError (e.g. 500) raises StorageException."""
    mock_s3 = MagicMock()
    error_response = {"Error": {"Code": "500", "Message": "Internal Error"}}
    mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

    adapter = StorageAdapter(bucket_name="test-bucket", s3_client=mock_s3)
    with pytest.raises(StorageException) as exc_info:
        adapter.verify_object_exists("blobs/error.enc")
    assert "Storage verification failed" in str(exc_info.value)


def test_storage_adapter_delete_object():
    """Verify delete_object delegates to S3 client delete_object."""
    mock_s3 = MagicMock()
    adapter = StorageAdapter(bucket_name="test-bucket", s3_client=mock_s3)

    adapter.delete_object("blobs/delete_me.enc")
    mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="blobs/delete_me.enc")


def test_storage_adapter_put_and_get_bytes():
    """Verify direct bytes upload and download with S3 client."""
    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {"ETag": '"abcde123"'}
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"encrypted_ciphertext_bytes")}

    adapter = StorageAdapter(bucket_name="test-bucket", s3_client=mock_s3)

    size, etag = adapter.put_object_bytes("blobs/data.bin", b"test_payload")
    assert size == len(b"test_payload")
    assert etag == "abcde123"

    retrieved = adapter.get_object_bytes("blobs/data.bin")
    assert retrieved == b"encrypted_ciphertext_bytes"


def test_in_memory_storage_adapter_lifecycle():
    """Verify complete in-memory storage adapter lifecycle for tests."""
    adapter = InMemoryStorageAdapter(bucket_name="memory-vault")
    object_key = "blobs/mem_test.enc"
    payload = b"test_secret_ciphertext_payload_12345"

    # 1. Before upload: does not exist
    exists, size, etag = adapter.verify_object_exists(object_key)
    assert exists is False
    assert size == 0

    # 2. Put bytes
    uploaded_size, uploaded_etag = adapter.put_object_bytes(object_key, payload)
    assert uploaded_size == len(payload)
    assert uploaded_etag != ""

    # 3. After upload: exists
    exists_now, size_now, etag_now = adapter.verify_object_exists(object_key)
    assert exists_now is True
    assert size_now == len(payload)
    assert etag_now == uploaded_etag

    # 4. Read bytes
    content = adapter.get_object_bytes(object_key)
    assert content == payload

    # 5. Presigned URLs
    up_url = adapter.generate_presigned_upload_url(object_key)
    down_url = adapter.generate_presigned_download_url(object_key)
    assert "action=put" in up_url
    assert "action=get" in down_url

    # 6. Delete
    adapter.delete_object(object_key)
    exists_after, _, _ = adapter.verify_object_exists(object_key)
    assert exists_after is False

    with pytest.raises(StorageException):
        adapter.get_object_bytes(object_key)


def test_get_and_set_storage_adapter_global():
    """Verify get_storage_adapter and set_storage_adapter dependency management."""
    custom = InMemoryStorageAdapter(bucket_name="custom-vault")
    set_storage_adapter(custom)
    try:
        active = get_storage_adapter()
        assert active is custom
        assert active.bucket_name == "custom-vault"
    finally:
        set_storage_adapter(None)
