---
name: Large tool output
description: Avoid treating large shell callback output as a complete structured document.
---

For large structured output, write a temporary file and read it with the file callback before parsing it.

**Why:** The shell callback silently lost the beginning of a large Git manifest even with a larger requested output budget. It also did not preserve Git's tab and NUL separators reliably.

**How to apply:** Serialize structured shell results as JSON into a temporary file, then read that file with an explicit byte budget. Prefer the normal shell tool for standalone commands; do not assume a successful exit proves captured stdout is complete.