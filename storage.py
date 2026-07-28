"""Canonical assignment/session storage boundary with local and GCS backends."""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from threading import Lock

from google.api_core.exceptions import PreconditionFailed

import config
from manifest import CANONICAL_MANIFEST_NAME
from observability import record_metric

CANONICAL_PDF_NAME = "assignment.pdf"
SESSION_PREFIX = "sessions/"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,127}$")


class StorageConflict(RuntimeError):
    """Raised when a conditional object write loses a concurrent update race."""


_LOCAL_SESSION_WRITE_LOCK = Lock()


def _check_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError("Malformed storage identifier")
    return value


def assignment_pdf_path(assignment_id: str) -> str:
    return f"assignments/{_check_id(assignment_id)}/{CANONICAL_PDF_NAME}"


def assignment_manifest_path(assignment_id: str) -> str:
    return f"assignments/{_check_id(assignment_id)}/{CANONICAL_MANIFEST_NAME}"


def session_blob_path(session_id: str) -> str:
    return f"{SESSION_PREFIX}{_check_id(session_id)}.json"


def assignment_prefix(assignment_id: str) -> str:
    return f"assignments/{_check_id(assignment_id)}/"


def is_local_backend() -> bool:
    return config.STORAGE_BACKEND == "local"


def _local_root() -> Path:
    raw = Path(config.LOCAL_STORAGE_DIR)
    root = raw if raw.is_absolute() else config.ROOT / raw
    root = root.resolve()
    if root.is_symlink():
        raise RuntimeError("Local storage root must not be a symlink")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def _local_path(relative: str) -> Path:
    root = _local_root()
    path = root / relative
    if ".." in Path(relative).parts:
        raise ValueError("Storage path escapes local root")
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise RuntimeError("Local storage path must not traverse symlinks")
    return path


def get_gcs_bucket():
    """Compatibility seam for GCS tests and production backend operations."""
    return config.get_gcs_bucket()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise RuntimeError("Local storage target must not be a symlink")
    fd, temporary = tempfile.mkstemp(prefix=".claros-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _generation(payload: bytes) -> int:
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _gcs_path(path: str) -> str:
    return f"gs://{get_gcs_bucket().name}/{path}"


def upload_pdf_to_gcs(assignment_id: str, pdf_bytes: bytes) -> str:
    path = assignment_pdf_path(assignment_id)
    if is_local_backend():
        _atomic_write(_local_path(path), pdf_bytes)
        return f"file://{_local_path(path)}"
    blob = get_gcs_bucket().blob(path)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    return _gcs_path(path)


def download_pdf_bytes(assignment_id: str) -> bytes:
    path = assignment_pdf_path(assignment_id)
    if is_local_backend():
        local = _local_path(path)
        if local.is_symlink():
            raise RuntimeError("Local storage assignment must not be a symlink")
        if not local.exists():
            raise ValueError("Assignment not found")
        return local.read_bytes()
    bucket = get_gcs_bucket()
    blob = bucket.blob(path)
    if blob.exists():
        return blob.download_as_bytes()
    blobs = sorted(bucket.list_blobs(prefix=assignment_prefix(assignment_id)), key=lambda item: item.name)
    pdfs = [item for item in blobs if item.name.lower().endswith(".pdf")]
    if not pdfs:
        raise ValueError("Assignment not found")
    return pdfs[0].download_as_bytes()


def upload_manifest_to_gcs(assignment_id: str, manifest_json: str) -> str:
    path = assignment_manifest_path(assignment_id)
    payload = manifest_json.encode("utf-8")
    if is_local_backend():
        _atomic_write(_local_path(path), payload)
        return f"file://{_local_path(path)}"
    blob = get_gcs_bucket().blob(path)
    blob.upload_from_string(payload, content_type="application/json")
    return _gcs_path(path)


def download_manifest_from_gcs(assignment_id: str) -> bytes | None:
    path = assignment_manifest_path(assignment_id)
    if is_local_backend():
        local = _local_path(path)
        if not local.exists() or local.is_symlink():
            return None
        return local.read_bytes()
    blob = get_gcs_bucket().blob(path)
    return blob.download_as_bytes() if blob.exists() else None


def delete_assignment_prefix(assignment_id: str) -> None:
    prefix = assignment_prefix(assignment_id)
    if is_local_backend():
        directory = _local_path(prefix)
        if directory.exists():
            if directory.is_symlink():
                raise RuntimeError("Local storage assignment must not be a symlink")
            for item in directory.iterdir():
                if item.is_symlink() or not item.is_file():
                    raise RuntimeError("Local storage assignment has unsafe contents")
                item.unlink()
            directory.rmdir()
        return
    for blob in get_gcs_bucket().list_blobs(prefix=prefix):
        blob.delete()


def upload_session_to_gcs(session_id: str, payload: bytes, if_generation_match: int | None = None, *, return_generation: bool = False):
    path = session_blob_path(session_id)
    if is_local_backend():
        local = _local_path(path)
        with _LOCAL_SESSION_WRITE_LOCK:
            if local.exists():
                existing = local.read_bytes()
                if if_generation_match is not None and _generation(existing) != if_generation_match:
                    record_metric("write_conflict", status="conflict", reason="storage")
                    raise StorageConflict(f"Session changed concurrently: {session_id}")
            elif if_generation_match not in (None, 0):
                raise StorageConflict(f"Session changed concurrently: {session_id}")
            _atomic_write(local, payload)
            result = (f"file://{local}", _generation(payload))
            return result if return_generation else result[0]
    blob = get_gcs_bucket().blob(path)
    try:
        kwargs = {"content_type": "application/json"}
        if if_generation_match is not None:
            kwargs["if_generation_match"] = if_generation_match
        blob.upload_from_string(payload, **kwargs)
    except PreconditionFailed as exc:
        record_metric("write_conflict", status="conflict", reason="storage")
        raise StorageConflict(f"Session changed concurrently: {session_id}") from exc
    result = (_gcs_path(path), getattr(blob, "generation", None))
    return result if return_generation else result[0]


def download_session_from_gcs(session_id: str, *, with_generation: bool = False):
    path = session_blob_path(session_id)
    if is_local_backend():
        local = _local_path(path)
        if not local.exists() or local.is_symlink():
            raise ValueError("Session not found")
        payload = local.read_bytes()
        return (payload, _generation(payload)) if with_generation else payload
    blob = get_gcs_bucket().blob(path)
    if not blob.exists():
        raise ValueError("Session not found")
    payload = blob.download_as_bytes()
    return (payload, getattr(blob, "generation", None)) if with_generation else payload


def delete_session_from_gcs(session_id: str) -> None:
    path = session_blob_path(session_id)
    if is_local_backend():
        local = _local_path(path)
        if local.exists():
            if local.is_symlink():
                raise RuntimeError("Local storage session must not be a symlink")
            local.unlink()
        return
    blob = get_gcs_bucket().blob(path)
    if blob.exists():
        blob.delete()


def delete_assignment_and_sessions(assignment_id: str) -> None:
    delete_assignment_prefix(assignment_id)
