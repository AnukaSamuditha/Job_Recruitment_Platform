"""S3-compatible object storage (MinIO) for CV binaries."""

from __future__ import annotations

import uuid
from typing import BinaryIO

import boto3
from botocore.client import BaseClient

from app.core.config import Settings, get_settings


class MinioStorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._bucket = self._settings.minio_bucket
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=self._settings.minio_endpoint,
            aws_access_key_id=self._settings.minio_access_key,
            aws_secret_access_key=self._settings.minio_secret_key,
            use_ssl=self._settings.minio_use_ssl,
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    def put_cv(
        self,
        job_id: uuid.UUID,
        filename: str,
        body: bytes | BinaryIO,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload CV bytes; returns object key."""
        safe_name = filename.replace("\\", "/").split("/")[-1][:240]
        key = f"jobs/{job_id}/cvs/{uuid.uuid4().hex}_{safe_name}"
        extra = {"ContentType": content_type}
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=body, **extra
        )
        return key

    def get_object_bytes(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()
