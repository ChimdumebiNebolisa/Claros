# Claros storage architecture

`storage.py` is the canonical persistence boundary for assignment PDFs,
manifests, sessions, cleanup, and optimistic session generations. Assignment
services use it for upload, page rendering, export-source retrieval, and
expiration cleanup; session services use it for all session reads/writes.

Development offline demo mode uses `CLAROS_STORAGE_BACKEND=local` and stores
data below `.claros-data/assignments/<id>/`, `.claros-data/sessions/`, and
`.claros-data/exports/`. Production requires `CLAROS_STORAGE_BACKEND=gcs` and
`GCS_BUCKET_NAME` at startup. Local mode is refused in production.

The local backend allows only bounded alphanumeric/hyphen IDs, resolves paths
under one root, refuses symlink roots/descendants/targets, and atomically
replaces PDF, manifest, and session files after flush. Session generation is a
content hash; stale conditional writes raise `StorageConflict`, matching the
GCS precondition behavior. Expiration remains enforced by the manifest and
session services, which delete expired records through this boundary.

Known limitation: local storage is single-host development storage; it is not
a shared production concurrency solution.
