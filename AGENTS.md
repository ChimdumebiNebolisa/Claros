# Claros working agreements

Claros helps students with typing barriers complete validated short-answer PDFs
with one deterministic answer area per question. The active reconstruction is
planned in `openspec/changes/claros-reconstruction/` and is governed by the
supplied PRD and `docs/CLAROS_DESIGN.md`.

## Engineering

Before non-trivial code, architecture, schema, integration, or refactoring,
read `docs/agents/engineering.md`.

- Keep exact-answer confirmation, deterministic placement, immutable source
  pages, and server-owned export invariants intact.
- Keep typed input complete when voice is unavailable; microphone access is
  optional and voice cannot commit, export, or control geometry.
- Use the active OpenSpec design as the source of truth for substantive
  requirement, architecture, and surface-authority changes.
- Preserve the supplied design system; do not introduce a competing token or
  component foundation.
