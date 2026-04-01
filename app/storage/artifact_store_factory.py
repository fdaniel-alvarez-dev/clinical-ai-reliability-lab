from __future__ import annotations

from app.core.settings import Settings
from app.storage.artifact_store import (
    ArtifactStore,
    GCSArtifactStore,
    LocalArtifactStore,
    S3ArtifactStore,
)


def artifact_store_from_settings(*, settings: Settings) -> ArtifactStore:
    store = settings.artifact_store.lower().strip()
    if store == "local":
        return LocalArtifactStore(root_dir=settings.artifacts_dir, prefix="")

    bucket = settings.artifact_store_bucket
    if not bucket:
        raise RuntimeError("ARTIFACT_STORE_BUCKET is required for non-local artifact stores.")

    if store in {"s3", "r2"}:
        return S3ArtifactStore(
            bucket=bucket,
            prefix=settings.artifact_store_prefix,
            endpoint_url=settings.artifact_store_s3_endpoint_url,
            region_name=settings.artifact_store_s3_region,
        )

    if store == "gcs":
        return GCSArtifactStore(bucket=bucket, prefix=settings.artifact_store_prefix)

    raise RuntimeError(f"Unknown ARTIFACT_STORE={settings.artifact_store!r}")
