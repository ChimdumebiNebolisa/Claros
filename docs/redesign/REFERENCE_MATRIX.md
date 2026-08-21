# Visual Reference Matrix

Research date: 2026-08-21 (live browser capture from the experiment worktree)

The screenshots below are reconnaissance evidence, not runtime assets. They are
stored under the ignored `output/playwright/` evidence directory so the product
does not acquire third-party assets or scripts.

## 1. Linear

- URL: [linear.app/features](https://linear.app/features)
- Evidence: `output/playwright/reference-linear-features-desktop.png` and
  `output/playwright/reference-linear-features.png`
- Useful surface: public hero, feature proof, product navigation.
- Useful pattern: a restrained dark canvas, short product claims, and a sequence
  of real product capabilities that feels like a workflow rather than a generic
  feature grid. Mobile turns each capability into a readable, tappable unit.
- Relevant to Claros: use a clear narrative spine for capture → review → write
  and make the product proof carry more weight than decorative marketing cards.
- Do not copy: dark palette, Linear mark, circular glyphs, feature labels,
  motion language, or exact stacked-card composition.

## 2. Khan Academy

- URL: [khanacademy.org](https://www.khanacademy.org/)
- Evidence: `output/playwright/reference-khan-home-desktop.png` and
  `output/playwright/reference-khan-home.png`
- Useful surface: education promise, learner pathways, progress/proof, mobile
  content rhythm.
- Useful pattern: plain-language mission, clear role entry, visible progress,
  and evidence of breadth presented without pretending a learner is a metric.
- Relevant to Claros: maintain a student-first tone, use progression as
  orientation, and describe access and confidence before introducing AI.
- Do not copy: Khan Academy colors, mascot/illustration language, statistics,
  course taxonomy, or card layouts.

## 3. Readwise Reader documentation / PDF workflow

- URL: [Readwise PDF FAQ](https://docs.readwise.io/reader/docs/faqs/pdfs)
- Evidence: `output/playwright/reference-readwise-pdf-docs-desktop.png` and
  `output/playwright/reference-readwise-pdf-docs.png`
- Useful surface: document reading, PDF controls, side-panel mental model,
  keyboard and mobile guidance.
- Useful pattern: document-specific help is organized around real reading jobs
  (zoom, snapshot, export, text view), with keyboard shortcuts and mobile
  alternatives made explicit.
- Relevant to Claros: explain physical worksheet versus side-panel fallback as
  a first-class document workflow, not as a generic error state.
- Do not copy: Reader branding, documentation chrome, highlight colors, exact
  sidebar/annotation layout, or proprietary copy/screenshots.

## 4. Descript

- URL: [Descript editor interface](https://help.descript.com/descript-tour/the-editor-interface)
- Evidence: `output/playwright/reference-descript-editor-desktop.png` and
  `output/playwright/reference-descript-editor.png`
- Useful surface: text-first editor, contextual sidebar, optional AI/voice
  tools, and explanatory product diagrams.
- Useful pattern: name the primary working surface first (script/editor), then
  clarify supporting canvas, timeline, and sidebar roles. The documentation
  makes “what changes what” concrete.
- Relevant to Claros: keep the answer editor and task context central while
  making document canvas, transcript, and status controls subordinate but
  discoverable.
- Do not copy: Descript red, editor diagram, timeline metaphor, product names,
  or AI co-editor behavior.

## 5. Notion

- URL: [Notion product](https://www.notion.com/product)
- Evidence: `output/playwright/reference-notion-product.png` (mobile capture;
  the redirect resolved from `notion.so/product`) 
- Useful surface: concise product positioning, composable workspace proof,
  entry CTA, trust and use-case grouping.
- Useful pattern: the page moves from a single human promise into a few concrete
  “jobs to be done,” then returns to a simple starting action. The visuals show
  products in use instead of abstract AI claims.
- Relevant to Claros: frame each section around a student job and show exact
  state transitions with real-looking worksheet context.
- Do not copy: Notion logo, emoji/avatar row, “where teams and agents ship”
  wording, exact use-case cards, or brand colors.

## Synthesis decisions

The redesign borrows only these cross-reference principles:

1. Lead with the student job and product boundary, not AI novelty.
2. Use real worksheet/document evidence as the hero proof.
3. Make progression and state transitions visually scannable.
4. Treat side-panel, keyboard, and export behavior as product value.
5. Let one primary work surface dominate each screen; supporting controls form
   a calm rail rather than a dashboard grid.

The redesign explicitly rejects the common reference failure modes: gradient
AI-SaaS washes, opaque “magic” answer claims, copied brand colors/illustrations,
metric tiles without a student job, and cards nested inside cards without a
behavioral purpose.
