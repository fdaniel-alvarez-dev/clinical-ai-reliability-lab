from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _join(prefix: str, name: str) -> str:
    a = prefix.strip("/ ")
    b = name.strip("/ ")
    if not a:
        return b
    if not b:
        return a
    return f"{a}/{b}"


@dataclass(frozen=True)
class ArtifactAddress:
    """
    A stable reference used in API payloads.

    For `local` this is a relative path under ARTIFACTS_DIR.
    For remote stores this is typically an object key or URI.
    """

    ref: str


class ArtifactStore(ABC):
    @abstractmethod
    def scoped(self, *, prefix: str) -> ArtifactStore: ...

    @abstractmethod
    def put_text(self, *, name: str, content: str, encoding: str = "utf-8") -> ArtifactAddress: ...

    @abstractmethod
    def put_bytes(self, *, name: str, content: bytes) -> ArtifactAddress: ...

    def put_json(self, *, name: str, payload: Any) -> ArtifactAddress:
        return self.put_text(
            name=name,
            content=json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )


class LocalArtifactStore(ArtifactStore):
    def __init__(self, *, root_dir: str, prefix: str = "") -> None:
        self._root_dir = Path(root_dir)
        self._prefix = prefix

    def scoped(self, *, prefix: str) -> ArtifactStore:
        return LocalArtifactStore(root_dir=str(self._root_dir), prefix=_join(self._prefix, prefix))

    def put_text(self, *, name: str, content: str, encoding: str = "utf-8") -> ArtifactAddress:
        path = self._path_for(name=name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return ArtifactAddress(ref=self._ref_for(name=name))

    def put_bytes(self, *, name: str, content: bytes) -> ArtifactAddress:
        path = self._path_for(name=name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return ArtifactAddress(ref=self._ref_for(name=name))

    def _ref_for(self, *, name: str) -> str:
        return _join(self._prefix, name)

    def _path_for(self, *, name: str) -> Path:
        rel = self._ref_for(name=name)
        return self._root_dir / rel


class S3ArtifactStore(ArtifactStore):
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region_name: str | None = None,
    ) -> None:
        try:
            import boto3  # type: ignore[import-not-found,import-untyped]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("boto3 is required for S3ArtifactStore. Install extra: storage-s3") from exc
        self._bucket = bucket
        self._prefix = prefix
        self._endpoint_url = endpoint_url
        self._region_name = region_name
        self._client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region_name)

    def scoped(self, *, prefix: str) -> ArtifactStore:
        return S3ArtifactStore(
            bucket=self._bucket,
            prefix=_join(self._prefix, prefix),
            endpoint_url=self._endpoint_url,
            region_name=self._region_name,
        )

    def put_text(self, *, name: str, content: str, encoding: str = "utf-8") -> ArtifactAddress:
        data = content.encode(encoding)
        return self.put_bytes(name=name, content=data)

    def put_bytes(self, *, name: str, content: bytes) -> ArtifactAddress:
        key = _join(self._prefix, name)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
        return ArtifactAddress(ref=f"s3://{self._bucket}/{key}")


class GCSArtifactStore(ArtifactStore):
    def __init__(self, *, bucket: str, prefix: str = "") -> None:
        try:
            from google.cloud import storage  # type: ignore[import-not-found,import-untyped]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "google-cloud-storage is required for GCSArtifactStore. Install extra: storage-gcs"
            ) from exc
        self._bucket_name = bucket
        self._prefix = prefix
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)

    def scoped(self, *, prefix: str) -> ArtifactStore:
        return GCSArtifactStore(bucket=self._bucket_name, prefix=_join(self._prefix, prefix))

    def put_text(self, *, name: str, content: str, encoding: str = "utf-8") -> ArtifactAddress:
        blob_name = _join(self._prefix, name)
        blob = self._bucket.blob(blob_name)
        blob.upload_from_string(content, content_type="text/plain", client=self._client)
        return ArtifactAddress(ref=f"gs://{self._bucket_name}/{blob_name}")

    def put_bytes(self, *, name: str, content: bytes) -> ArtifactAddress:
        blob_name = _join(self._prefix, name)
        blob = self._bucket.blob(blob_name)
        blob.upload_from_string(content, client=self._client)
        return ArtifactAddress(ref=f"gs://{self._bucket_name}/{blob_name}")
