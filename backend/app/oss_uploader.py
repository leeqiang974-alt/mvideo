"""Aliyun OSS image uploader for the M.Video Excel-import pipeline (v0.3).

The M.Video product-import template expects PUBLIC image URLs. Ozon CDN URLs
are not durable / may be geo-blocked, so the pipeline mirrors processed
3:4 images into our own OSS bucket and stores those public URLs on the item
(``oss_images_json``).

This class is a thin, dependency-light wrapper. ``oss2`` is imported lazily so
unit tests can inject a fake uploader (any object exposing
``upload_image_file(path, key) -> url``) without installing oss2. Secrets are
read from settings/env and are NEVER logged, repr'd, or printed — only the
returned public URL is surfaced.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

log = logging.getLogger("mvideo.oss")


class OssUploader:
    """Upload processed product images to Aliyun OSS; return public URLs.

    Credentials come from app.config (env): OSS_ENDPOINT / OSS_BUCKET /
    OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_PUBLIC_BASE. The object
    holds them only for the lifetime of the bucket handle and never logs them.
    """

    def __init__(
        self,
        *,
        endpoint: str = "",
        bucket: str = "",
        access_key_id: str = "",
        access_key_secret: str = "",
        public_base: str = "",
    ) -> None:
        self._endpoint = (endpoint or "").strip().rstrip("/")
        self._bucket_name = (bucket or "").strip()
        self._ak = (access_key_id or "").strip()
        self._sk = (access_key_secret or "").strip()
        self._public_base = (public_base or "").strip().rstrip("/")
        self._bucket_handle: Any = None  # lazy oss2.Bucket

    # ------------------------------------------------------------------ #
    @classmethod
    def from_settings(cls) -> "OssUploader":
        from .config import get_settings

        s = get_settings()
        # Explicit OSS_* env wins; otherwise fall back to the shared Aliyun
        # credential file (line[1]=AccessKeyId, line[3]=AccessKeySecret).
        if s.oss_access_key_id and s.oss_access_key_secret:
            return cls(
                endpoint=s.oss_endpoint,
                bucket=s.oss_bucket,
                access_key_id=s.oss_access_key_id,
                access_key_secret=s.oss_access_key_secret,
                public_base=s.oss_public_base,
            )
        return cls.from_credential_file(s.oss_credential_file)

    @classmethod
    def from_credential_file(cls, path: str = "") -> "OssUploader":
        """Build an uploader from the shared Aliyun key file.

        File format (non-blank lines): 0=label, 1=AccessKeyId (LTAI...),
        2=label, 3=AccessKeySecret. Default endpoint/bucket match the proven
        SKU00259 setup. Values are never logged.
        """
        import pathlib

        p = pathlib.Path(path or os.getenv("ALIYUN_OSS_CREDENTIAL_FILE", "")).expanduser()
        lines = [
            x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()
        ]
        if len(lines) < 4:
            raise RuntimeError(f"OSS credential file too short: {p}")
        return cls(
            endpoint="oss-cn-shanghai.aliyuncs.com",
            bucket="ozonshanghai",
            access_key_id=lines[1],
            access_key_secret=lines[3],
            public_base="",
        )

    def _bucket(self) -> Any:
        if self._bucket_handle is not None:
            return self._bucket_handle
        if not (self._endpoint and self._bucket_name and self._ak and self._sk):
            raise RuntimeError(
                "OSS not configured (OSS_ENDPOINT/OSS_BUCKET/OSS_ACCESS_KEY_ID/"
                "OSS_ACCESS_KEY_SECRET missing)"
            )
        import oss2  # lazy: only needed for a real upload

        auth = oss2.Auth(self._ak, self._sk)
        self._bucket_handle = oss2.Bucket(
            auth, f"https://{self._endpoint}", self._bucket_name, connect_timeout=15
        )
        return self._bucket_handle

    def _public_url(self, object_key: str) -> str:
        if self._public_base:
            return f"{self._public_base}/{object_key}"
        # default: https://<bucket>.<endpoint>/<key>
        ep = self._endpoint.replace("https://", "").replace("http://", "")
        return f"https://{self._bucket_name}.{ep}/{object_key}"

    # ------------------------------------------------------------------ #
    def upload_image_file(self, local_path: str, object_key: str, *, verify: bool = True) -> str:
        """Upload one local image file; return its public OSS URL.

        Only the returned URL is logged. Raises FileNotFoundError / RuntimeError
        on failure; never prints credentials.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(local_path)
        bucket = self._bucket()
        ct = mimetypes.guess_type(local_path)[0] or "image/jpeg"
        bucket.put_object_from_file(object_key, local_path, headers={"Content-Type": ct})
        url = self._public_url(object_key)
        if verify:
            meta = bucket.head_object(object_key)
            if getattr(meta, "status", 200) != 200:
                raise RuntimeError(f"OSS HEAD verify failed: {object_key}")
        log.info("oss uploaded %s -> %s", object_key, url)  # url only, no secret
        return url

    def close(self) -> None:
        self._bucket_handle = None
