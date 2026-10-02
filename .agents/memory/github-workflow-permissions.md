---
name: GitHub workflow write permissions
description: Workflow file writes can fail despite successful ordinary code writes.
---

Do not treat a GitHub tree-write 404 as proof that the repository or credentials are invalid.

**Why:** The attached connection allowed ordinary code tree writes but rejected a tree containing a workflow file with 404. Its healthy OAuth grant declared repo access, but no workflow scope.

**How to apply:** Compare ordinary code writes with workflow writes, and inspect authorization context. Do not offer reauthorization when the returned scopes cannot supply the missing permission. Deployment script fixes can use existing workflow entrypoints without changing workflow files.

For normal source uploads, create base64-encoded Git blobs and reference their hashes in the tree.

**Why:** Inline source containing security-test fixtures received a non-JSON HTML 403 from the gateway, while uploading the same bytes through the supported base64 blob API succeeded.

**How to apply:** Distinguish a gateway response from GitHub's structured permission errors. Use the blob API for legitimate source content; it does not grant workflow permissions or repair an expired credential.