---
name: Package installation portability
description: Managed installs may change the active Node runtime and write internal registry URLs into locks.
---

Check the active runtime and lockfile URLs after managed package installation.

**Why:** A managed npm install used Node 20 despite this project's Node 22 engine requirement, changed an exact dependency pin into a range, and wrote Replit-internal package URLs. Those URLs cannot be fetched by GitHub Actions.

**How to apply:** Preserve exact dependency pins, keep committed npm lockfile URLs on the public registry, and run checks with a Node 22 executable. Never weaken security scans to get a deployment through.