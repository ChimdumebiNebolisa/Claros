# Claros storage architecture

`storage.py` is the canonical persistence boundary for assignment PDFs,
manifests, sessions, cleanup, and optimistic session generations. Assignment
services use it for upload, page rendering, export-source retrieval, and
explicit deletion; session services use it for all session reads/writes.

Development offline demo mode uses `CLAROS_STORAGE_BACKEND=local` and stores
data below `.claros-data/assignments/<id>/` and `.claros-data/sessions/`.
Production requires `CLAROS_STORAGE_BACKEND=gcs` and `GCS_BUCKET_NAME` at
startup. Local mode is refused in production.

The local backend allows only bounded alphanumeric/hyphen IDs, resolves paths
under one root, refuses symlink roots/descendants/targets, and atomically
replaces PDF, manifest, and session files after flush. Session generation is a
content hash; stale conditional writes raise `StorageConflict`, matching the
GCS precondition behavior.

## Retention honesty

- `SESSION_TTL_HOURS` (default 48): expired **session** blobs are deleted on
  access, and their assignment `.ref` markers are removed.
- `ASSIGNMENT_TTL_DAYS` (default 90): expired **assignments** return HTTP 410
  on access. That is a logical access stop. Claros does **not** claim automatic
  physical deletion of assignment PDFs/manifests on TTL alone.
- Physical removal of assignment PDFs, manifests, and registered sessions
  happens on explicit `DELETE /api/assignments/{id}` (capability required).

Known limitation: local storage is single-host development storage; it is not
a shared production concurrency solution. In-process rate limits are prototype
safeguards and are not distributed across Cloud Run instances.
