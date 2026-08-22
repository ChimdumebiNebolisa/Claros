# Claros design reference

The canonical visual source is the supplied `CLAROS_DESIGN.md` reference dated
2026-08-21. It is intentionally kept outside generated UI state; this compact
pointer keeps the repository honest while the full source remains available to
the build owner.

Core rules carried into implementation:

- light-first institutional workspace; monochrome surfaces with Glacier Tint
  `#e2e7fc` as the only routine accent;
- Inter, 8px rhythm, 2px corners, hairline borders, restrained shadows;
- worksheet is the visual anchor and the final answer field is distinct from
  tutoring transcript and voice controls;
- one primary action per state, placement visible before commit, and no
  pre-export language that implies PDF mutation;
- responsive desktop split workspace collapses to worksheet/answer views on
  mobile; keyboard and reduced-motion behavior stay complete.

The full supplied design file remains the controlling reference for details,
copy, states, tokens, and responsive rules.
