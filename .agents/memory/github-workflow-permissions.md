---
name: GitHub workflow write permissions
description: Workflow file writes can fail despite successful ordinary code writes.
---

Do not treat a GitHub tree-write 404 as proof that the repository or credentials are invalid.

**Why:** The attached connection allowed ordinary code tree writes but rejected a tree containing a workflow file with 404. Its healthy OAuth grant declared repo access, but no workflow scope.

**How to apply:** Compare ordinary code writes with workflow writes, and inspect authorization context. Do not offer reauthorization when the returned scopes cannot supply the missing permission. Deployment script fixes can use existing workflow entrypoints without changing workflow files.