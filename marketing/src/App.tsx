import * as React from "react"
import {
  AccessibilityIcon,
  CheckIcon,
  FileCheck2Icon,
  KeyboardIcon,
  LockKeyholeIcon,
  PanelRightIcon,
  ShieldCheckIcon,
} from "lucide-react"

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { ProductPreview } from "@/components/product-preview"

const EXACT_ANSWER =
  "Clear water has more insects, so it offers fish more food."

function DecisionReceipt() {
  const [written, setWritten] = React.useState(false)

  return (
    <Card className="decision-card" aria-live="polite">
      <CardHeader className="decision-header">
        <Badge
          variant={written ? "default" : "outline"}
          className={written ? "success-label" : "confirmed-label"}
        >
          {written ? <CheckIcon aria-hidden="true" /> : <LockKeyholeIcon aria-hidden="true" />}
          {written ? "Added to export" : "Confirmed, not written"}
        </Badge>
        <CardTitle>One answer. Two separate decisions.</CardTitle>
      </CardHeader>
      <CardContent className="decision-content">
        <blockquote>{EXACT_ANSWER}</blockquote>
        <Separator />
        <dl>
          <div>
            <dt>Worksheet</dt>
            <dd>{written ? "Original page preserved" : "Unchanged"}</dd>
          </div>
          <div>
            <dt>Destination</dt>
            <dd>{written ? "Export side panel" : "Waiting for your choice"}</dd>
          </div>
        </dl>
      </CardContent>
      <CardFooter className="decision-footer">
        <Button
          type="button"
          variant="outline"
          className="decision-button"
          onClick={() => setWritten(false)}
        >
          Change answer
        </Button>
        <Button
          type="button"
          className="decision-button"
          onClick={() => setWritten(true)}
          disabled={written}
        >
          <PanelRightIcon aria-hidden="true" />
          {written ? "Added" : "Add to export"}
        </Button>
      </CardFooter>
    </Card>
  )
}

const FAQ_ITEMS = [
  {
    question: "Does Claros grade the answer?",
    answer:
      "No. Claros helps the student shape and review an answer. It does not present AI correctness grading.",
  },
  {
    question: "Which PDFs work best?",
    answer:
      "Worksheets with selectable text and clearly numbered tasks work best. Image-only scans may need OCR first.",
  },
  {
    question: "When does the microphone turn on?",
    answer:
      "Only after the student chooses voice guidance and grants browser permission. Typing remains available.",
  },
  {
    question: "Where are worksheets stored?",
    answer:
      "Uploaded PDFs and session state use the configured worksheet storage. Claros does not promise automatic timed deletion.",
  },
]

export function App() {
  return (
    <div className="site-shell" id="top">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <header className="site-header">
        <a href="#top" className="wordmark" aria-label="Claros home">
          Claros
        </a>
        <nav aria-label="Primary">
          <a href="#how-it-works">How it works</a>
          <a href="#safety">Safety</a>
          <a href="#faq">FAQ</a>
        </nav>
        <Button asChild className="header-cta">
          <a href="/app">Open worksheet</a>
        </Button>
      </header>

      <main id="main-content">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">Guided worksheet workspace</p>
            <h1 id="hero-title">Think it through. You decide.</h1>
            <p className="hero-intro">
              Shape the answer with guidance, review the exact words, then
              decide if and where they are written.
            </p>
            <Button asChild size="lg" className="hero-cta">
              <a href="/app?sample=canonical-short-answer-ecosystems">
                Try the sample
              </a>
            </Button>
          </div>
          <ProductPreview />
        </section>

        <section className="process-section" id="how-it-works" aria-labelledby="process-title">
          <div className="section-copy">
            <h2 id="process-title">The pause is part of the product.</h2>
            <p>
              Claros keeps thinking, confirmation, and writing distinct so the
              student always knows what will happen next.
            </p>
          </div>
          <ol className="process-list">
            <li>
              <FileCheck2Icon aria-hidden="true" />
              <div>
                <h3>Capture the reasoning</h3>
                <p>Type first, or ask for voice guidance when it helps.</p>
              </div>
            </li>
            <li>
              <ShieldCheckIcon aria-hidden="true" />
              <div>
                <h3>Review the exact words</h3>
                <p>See the full proposed answer before confirming anything.</p>
              </div>
            </li>
            <li>
              <PanelRightIcon aria-hidden="true" />
              <div>
                <h3>Choose the destination</h3>
                <p>Write only after confirmation, with a safe side panel when placement is uncertain.</p>
              </div>
            </li>
          </ol>
        </section>

        <section className="decision-section" aria-labelledby="decision-title">
          <div className="decision-copy">
            <h2 id="decision-title">Ready does not mean written.</h2>
            <p>
              Confirmation locks the exact answer. A separate action decides
              whether it reaches a verified line or the export side panel.
            </p>
            <div className="decision-facts">
              <span>
                <LockKeyholeIcon aria-hidden="true" />
                No silent writes
              </span>
              <span>
                <FileCheck2Icon aria-hidden="true" />
                Original pages preserved
              </span>
            </div>
          </div>
          <DecisionReceipt />
        </section>

        <section className="safety-section" id="safety" aria-labelledby="safety-title">
          <div className="safety-lead">
            <p className="eyebrow">Safety and access</p>
            <h2 id="safety-title">A clear boundary around every answer.</h2>
            <p>
              Placement follows deterministic evidence. Uncertainty never turns into guessed coordinates.
            </p>
          </div>
          <div className="safety-list">
            <article>
              <ShieldCheckIcon aria-hidden="true" />
              <div>
                <h3>Placement follows evidence</h3>
                <p>Verified regions can receive confirmed answers. Everything else uses the side panel.</p>
              </div>
            </article>
            <article>
              <KeyboardIcon aria-hidden="true" />
              <div>
                <h3>Typing always works</h3>
                <p>Microphone access is optional. The complete flow remains keyboard accessible.</p>
              </div>
            </article>
            <article>
              <AccessibilityIcon aria-hidden="true" />
              <div>
                <h3>The interface stays legible</h3>
                <p>Focus, reduced motion, zoom, and mobile targets are part of the product contract.</p>
              </div>
            </article>
          </div>
        </section>

        <section className="faq-section" id="faq" aria-labelledby="faq-title">
          <div className="faq-heading">
            <h2 id="faq-title">Useful details, plainly answered.</h2>
          </div>
          <Accordion type="single" collapsible className="faq-accordion">
            {FAQ_ITEMS.map((item) => (
              <AccordionItem key={item.question} value={item.question}>
                <AccordionTrigger>{item.question}</AccordionTrigger>
                <AccordionContent>
                  <p>{item.answer}</p>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      </main>

      <footer className="site-footer">
        <div>
          <strong>Claros</strong>
          <p>Guided worksheets with deliberate answers.</p>
        </div>
        <nav aria-label="Footer">
          <a href="/app">Open worksheet</a>
          <a href="#how-it-works">How it works</a>
          <a href="#safety">Safety</a>
        </nav>
        <p>© 2026 Claros</p>
      </footer>
    </div>
  )
}

export default App
