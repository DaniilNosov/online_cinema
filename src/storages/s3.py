import uuid
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException, status

from src.config.settings import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class S3StorageClient:
    """Client for managing file uploads to S3-compatible storage (MinIO)."""

    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    def _ensure_bucket_exists(self) -> None:
        """Create the S3 bucket if it does not already exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket_name)

    async def upload_avatar(self, user_id: int, file: UploadFile) -> str:
        """Validate and upload a user avatar image to S3, returning its URL."""
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Allowed formats: JPEG, PNG, WEBP",
            )

        self._ensure_bucket_exists()

        extension = ALLOWED_IMAGE_TYPES[file.content_type]
        file_key = f"avatars/user_{user_id}_{uuid.uuid4().hex}.{extension}"
        content = await file.read()

        self.client.put_object(
            Bucket=self.bucket_name,
            Key=file_key,
            Body=content,
            ContentType=file.content_type,
        )

        return f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{file_key}"


s3_client = S3StorageClient()
