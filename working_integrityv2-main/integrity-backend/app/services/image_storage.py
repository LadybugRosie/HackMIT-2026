"""
Image Storage Service - S3-based image storage
Replaces base64-in-MongoDB to prevent database bloat and protect biometric data.
Falls back to MongoDB if S3 is not configured (development).
"""

import os
import base64
import uuid
import logging
from typing import Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS Configuration (reuses same credentials as Rekognition)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_IMAGE_BUCKET", "editorrah-images")

# S3 client
s3_client = None
S3_AVAILABLE = False


def initialize_s3():
    """Initialize S3 client. Call during app startup."""
    global s3_client, S3_AVAILABLE

    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        logger.warning("AWS credentials not set – image storage will fall back to MongoDB (not recommended for production).")
        return False

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        # Ensure bucket exists (ignore if already exists)
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
            logger.info(f"S3 bucket '{S3_BUCKET}' is accessible.")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # Create bucket
                if AWS_REGION == "us-east-1":
                    s3_client.create_bucket(Bucket=S3_BUCKET)
                else:
                    s3_client.create_bucket(
                        Bucket=S3_BUCKET,
                        CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
                    )
                # Enable server-side encryption by default
                s3_client.put_bucket_encryption(
                    Bucket=S3_BUCKET,
                    ServerSideEncryptionConfiguration={
                        "Rules": [
                            {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                        ]
                    },
                )
                # Block public access
                s3_client.put_public_access_block(
                    Bucket=S3_BUCKET,
                    PublicAccessBlockConfiguration={
                        "BlockPublicAcls": True,
                        "IgnorePublicAcls": True,
                        "BlockPublicPolicy": True,
                        "RestrictPublicBuckets": True,
                    },
                )
                logger.info(f"Created S3 bucket '{S3_BUCKET}' with encryption and private access.")
            elif error_code == "403":
                logger.warning(f"S3 bucket '{S3_BUCKET}' access denied – check IAM permissions. Falling back to MongoDB.")
                S3_AVAILABLE = False
                return False
            else:
                raise

        S3_AVAILABLE = True
        logger.info("S3 image storage initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"S3 initialization failed: {e}")
        S3_AVAILABLE = False
        return False


def _parse_data_url(data_url: str) -> Tuple[str, bytes]:
    """Parse a data URL into content_type and raw bytes."""
    if data_url.startswith("data:"):
        header, encoded = data_url.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
        image_bytes = base64.b64decode(encoded)
        return content_type, image_bytes
    # Assume raw base64 JPEG
    return "image/jpeg", base64.b64decode(data_url)


async def upload_image(data_url: str, folder: str = "profiles", user_id: str = "") -> Optional[str]:
    """
    Upload a base64 data-URL image to S3.

    Returns the S3 key (path) on success, or None if S3 is unavailable
    (caller should fall back to storing the data_url in MongoDB for dev).
    """
    if not S3_AVAILABLE or not s3_client:
        return None

    try:
        content_type, image_bytes = _parse_data_url(data_url)
        ext = "png" if "png" in content_type else "jpg"
        key = f"{folder}/{user_id}/{uuid.uuid4().hex}.{ext}"

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        logger.info(f"Uploaded image to S3: {key} ({len(image_bytes)} bytes)")
        return key
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        return None


async def get_image_url(key: str, expires_in: int = 3600) -> Optional[str]:
    """
    Generate a pre-signed URL for an S3-stored image.
    URLs expire after `expires_in` seconds (default 1 hour).
    """
    if not S3_AVAILABLE or not s3_client or not key:
        return None

    # If the key is already a data URL (legacy), return as-is
    if key.startswith("data:"):
        return key

    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate pre-signed URL for {key}: {e}")
        return None


async def delete_image(key: str) -> bool:
    """Delete an image from S3."""
    if not S3_AVAILABLE or not s3_client or not key or key.startswith("data:"):
        return False

    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
        logger.info(f"Deleted image from S3: {key}")
        return True
    except Exception as e:
        logger.error(f"S3 delete failed: {e}")
        return False
