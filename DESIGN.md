# Design

Claros uses one quiet visual system across the public landing and worksheet
workspace. The implementation remains vanilla HTML, CSS, and JavaScript.

## Foundation

- Instrument Sans is served from the repository.
- The canvas is near-white; interactive surfaces are white.
- Dark navy carries primary text, cool gray carries secondary text and rules.
- Cobalt is reserved for focus and direct student actions.
- Green, amber, and red are semantic success, caution, and failure roles.
- Spacing follows an 8px base. Controls use 8px radii; major surfaces use 12px.
- Shadows are reserved for the rendered PDF page or genuinely elevated menus.

The shared values live in `frontend/styles/tokens.css`.

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
and real Review-state product evidence. The remaining order is the three-step
flow, a real confirmed-not-written state, combined safety/accessibility
information, a short FAQ, and a restrained footer. It uses spacing and rules
instead of feature cards, decorative rotation, or marketing effects.

Current visual and request evidence is indexed from `docs/VERIFICATION.md`.
