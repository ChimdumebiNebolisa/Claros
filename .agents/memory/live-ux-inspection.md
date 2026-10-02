---
name: Live UX inspection
description: How to audit the public Claros sample without configuring the imported application.
---

When the imported app is intentionally left unconfigured, inspect the public biology sample in a temporary headless Chromium session rather than installing the full OpenAI/Java/PDF stack merely for a visual audit. Static URL screenshots alone do not reveal the question, approval, and export states. In this environment's Node 20 shell, the built-in WebSocket client requires `--experimental-websocket` for Chrome DevTools Protocol interaction.

**Why:** The normal local runtime requires external services and system tools; temporary public-sample inspection respects the owner's decision not to set up the import. Static screenshot capture only showed the landing and upload screens, and two initial CDP connection attempts failed before the Node runtime flag was identified.

**How to apply:** Use the public sample only for read/interaction audits when the user authorizes a live-product inspection. Keep temporary browser profiles and captures outside the workspace; do not infer that one observed voice error or export result is universal.