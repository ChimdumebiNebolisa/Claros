---
name: Embedded preview verification
description: Verify public preview routing separately from localhost rendering and distinguish browser-test framing failures.
---

## Public preview routing

Keep the real homepage reachable through either preview service. Do not rely on repeatedly remapping platform-managed port exposure.

**Why:** Managed port exposure can reconcile back to the sandbox even after a manual correction has been verified. The homepage can render correctly on localhost while the public link reverts to the component-server placeholder.

**How to apply:** Preserve routing that serves the actual app at the public root regardless of which service receives the request. Keep namespaced mockup routes isolated to avoid proxy loops, and check the public URL after restarting services.

## Browser-test framing

Do not weaken the application's framing policy just because a synthetic iframe check fails with Local Network Access blocking.

**Why:** The test browser classified the development preview as a private-network destination when embedded by a simulated public Replit parent. The iframe rendered correctly once that browser-only check was isolated; the application’s framing policy was already compatible.

**How to apply:** Inspect request failures before changing application headers. For this container-specific test, disable Local Network Access checks only in the verification browser, not in the app or the user's browser.