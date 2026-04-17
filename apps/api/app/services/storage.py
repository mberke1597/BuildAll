import io
import boto3

from app.core.config import get_settings


def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
    )


def ensure_bucket():
    settings = get_settings()
    s3 = get_s3_client()
    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if settings.minio_bucket not in buckets:
        s3.create_bucket(Bucket=settings.minio_bucket)


def upload_bytes(key: str, data: bytes, content_type: str):
    settings = get_settings()
    s3 = get_s3_client()
    s3.put_object(Bucket=settings.minio_bucket, Key=key, Body=io.BytesIO(data), ContentType=content_type)


def get_presigned_url(key: str):
    settings = get_settings()
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": key},
        ExpiresIn=3600,
    )
