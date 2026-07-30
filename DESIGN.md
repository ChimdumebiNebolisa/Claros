# Design

Claros uses one quiet visual system across the public landing and worksheet
workspace. The worksheet remains vanilla HTML, CSS, and JavaScript. The public
landing is a prerendered React/Vite surface built from repository-owned
Shadcn source components.

## Foundation

- Instrument Sans is served from the repository for the worksheet workspace.
- The landing uses self-hosted Geist through its Shadcn theme.
- The canvas is near-white; interactive surfaces are white.
- Dark navy carries primary text, cool gray carries secondary text and rules.
- Cobalt is reserved for focus and direct student actions.
- Green, amber, and red are semantic success, caution, and failure roles.
- Spacing follows an 8px base. Controls use 8px radii; major surfaces use 12px.
- Shadows are reserved for the rendered PDF page or genuinely elevated menus.

Workspace values live in `frontend/styles/tokens.css`. Landing values live in
`marketing/src/index.css` and use Shadcn semantic tokens rather than ad-hoc
component colors.

## Workspace hierarchy

The worksheet is primary. At desktop widths the document uses approximately
two-thirds of the workspace and the answer panel uses one-third. The answer
panel is flat: spacing and rules separate sections, while borders identify
editable, proposed, confirmed, written, or failed content.

The visible response stages are:

1. Capture: current task, editable reasoning, optional voice, typed fallback,
   one privacy line, and Review answer.
2. Review: the exact proposed answer, Edit answer, and Confirm answer.
3. Confirmed: the fixed exact answer, Change answer, a destination-specific
   write action, and the unchanged-worksheet reminder.
4. Writing: the fixed answer remains visible while conflicting actions are
   disabled and progress is announced.
5. Written: one success treatment contains the answer and destination.
6. Failed write: Review returns with one failure message and requires a new
   confirmation.

Confirmation and write remain separate requests. Presentation must never imply
that confirmation changes the PDF.

## Mobile

At 700px and below, the mounted worksheet and answer panels are selected by a
persistent `Worksheet` / `Answer` switch. A newly loaded assignment opens on
Worksheet. Only explicit student input changes the mobile view, and the choice
survives resizing. Both panels remain mounted so draft and document state are
preserved.

Touch targets are at least 44px. Keyboard focus, typed-only completion, reduced
motion, and document controls remain supported.

## Landing

The landing uses a compact header, a two-column hero with one sample action,
and an interactive Shadcn product composition. The composition demonstrates
Capture, Review, Confirmed, and export-side-panel states locally without
calling worksheet APIs. It replaces the prior raster workspace captures.

The remaining order is the deliberate three-part flow, an interactive
confirmed-not-written decision receipt, combined safety/accessibility
information, a short Shadcn accordion, and a restrained footer. The page uses
spacing, type, and stateful controls instead of fabricated browser chrome,
decorative rotation, or screenshot images.

Vite builds the client bundle and a server-rendered snapshot. The checked-in
`frontend/landing.html` is prerendered for first paint and then hydrated for
the product-state interactions.

Current visual and request evidence is indexed from `docs/VERIFICATION.md`.
