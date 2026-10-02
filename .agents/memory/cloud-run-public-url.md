---
name: Cloud Run public URL validation
description: Cloud Run's advertised numeric URL can differ from its legacy status URL.
---

Align the app's exact public origin with the numeric URL advertised by Cloud Run. Obtain it from live service metadata, not a guessed hostname.

**Why:** Cloud Run printed a numeric project URL while the workflow configured the legacy status URL as the only trusted host. API smoke checks passed against that legacy URL while the advertised homepage returned “Invalid host header.”

**How to apply:** Check the public homepage itself after rollout, not only health or API endpoints. Keep exact-host validation enabled. Inspect staging and production service names: a successful staging rollout is not proof that a separate production promotion occurred.