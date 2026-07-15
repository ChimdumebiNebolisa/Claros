# Product

## Register

product

(The `/` landing page is a brand surface; the `/app` worksheet workspace is the product. Treat landing tasks in the brand register, app tasks in the product register.)

## Users

Students with typing difficulties — motor impairments, dyslexia, injury, or similar — working through structured worksheet assignments, often at home or in a classroom under ordinary lighting. They can reason through problems verbally but are blocked by manual text entry. Secondary audience: teachers, parents, and evaluators watching a demo.

## Product Purpose

Claros is a voice-guided worksheet assistant. Students upload a worksheet PDF, talk through each question with a real-time voice agent (Gemini Live), and Claros writes the answer into the correct field — but only after the student has stated or approved that answer for that specific question. Completed worksheets export as PDF.

Success looks like: a student completes a worksheet by thinking out loud, without typing, and without the tool doing the thinking for them.

## Core Product Rule (never weaken)

Claros must only write an answer after the student has stated or approved the answer for that specific question. Readiness is tracked per question. This gate is the product's integrity; UI must make "answer stated" and "writing" states unmistakable, never hide or blur them.

## Brand Personality

Calm, capable, trustworthy. A patient tutor, not a flashy gadget. Premium accessibility-focused learning tool: quiet confidence, generous space, grounded copy. No hype words ("revolutionary", "supercharge").

## Anti-references

- Generic AI-SaaS landing pages: rainbow/purple-blue gradient washes, gradient text, glassy card grids, hero-metric stat rows.
- Crypto/DeFi visual language and Aave branding, text, or assets (a screenshot was used only as a taste reference for polish, whitespace, and section rhythm).
- Hackathon-demo UI: cramped panels, gray-on-gray low contrast, nested cards.
- Anything that looks like it's bypassing schoolwork; the tone is supportive, not answer-vending.

## Design Principles

1. **Calm over clever** — whitespace, restrained color, and large readable type carry the premium feel; decoration never competes with the worksheet.
2. **The gate is visible** — answer-readiness and writing states are first-class visual states, always legible at a glance.
3. **Voice is the hero** — the live session console should feel like a real assistant, with clear listening / speaking / writing feedback.
4. **Accessible by default** — this is a tool for students with disabilities; contrast, focus states, reduced motion, and screen-reader attributes are non-negotiable.
5. **Grounded copy** — say what the product does in plain sentences; no superlatives.

## Accessibility & Inclusion

- WCAG 2.1 AA minimum: body text ≥4.5:1 contrast, large text ≥3:1.
- Visible focus rings on all interactive elements; never remove existing ARIA attributes or live regions.
- `prefers-reduced-motion` alternatives for all animation.
- Voice-first flow must remain fully operable by pointer alone (upload, session, edit answers, export).
- Answer fields stay obviously editable (contenteditable with visible affordance and placeholder).
