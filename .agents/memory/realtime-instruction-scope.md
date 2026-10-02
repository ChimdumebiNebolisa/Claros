---
name: Realtime instruction scope
description: Per-response instructions replace the session prompt, so a greeting override can discard grounded question context.
---

Keep greeting policy in the server-owned Realtime session prompt. Do not send a greeting-only `response.create.response.instructions` override.

**Why:** During a real conversation check, that override made the AI ask which example to discuss instead of using the question already on the page. Per-response instructions replace, rather than extend, the session instructions.

**How to apply:** Use a plain `response.create` for the initial reply. If a response override is necessary later, explicitly preserve all required grounded context and behavior.