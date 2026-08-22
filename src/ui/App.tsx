import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { ArrowRight, Check, Download, ShieldCheck, X } from "lucide-react";
import { Wordmark } from "./Brand";

const Workspace = lazy(() => import("./Workspace"));

function Landing() {
  return (
    <main className="marketing-page">
      <nav className="marketing-nav page-width">
        <Wordmark />
        <div className="marketing-links">
          <a href="#how-it-works">How it works</a>
          <a href="#supported">Supported worksheets</a>
          <Link className="button button-ghost" to="/app">
            Open workspace <ArrowRight size={16} />
          </Link>
        </div>
      </nav>

      <section className="hero page-width">
        <div className="hero-copy">
          <p className="eyebrow">A completion workspace for students who need less typing</p>
          <h1>Your worksheet, one safe answer at a time.</h1>
          <p className="hero-lede">
            Claros keeps the original page visible, separates thinking from the final answer, and makes the next safe action clear.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/app">
              Open Claros <ArrowRight size={17} />
            </Link>
            <a className="button button-ghost" href="/api/v1/demo.pdf" download>
              Download sample PDF <Download size={16} />
            </a>
          </div>
          <p className="hero-note"><ShieldCheck size={15} /> Exact answer approval before export</p>
        </div>

        <div className="hero-art" role="img" aria-label="Preview of a worksheet beside its final-answer review panel">
          <div aria-hidden="true">
            <div className="artifact-bar">
              <Wordmark linked={false} />
              <span>ecosystems-worksheet.pdf</span>
              <span>Question 2 of 3</span>
            </div>
            <div className="artifact-body">
              <div className="artifact-paper">
                <p className="paper-title">ECOSYSTEMS</p>
                <div className="paper-question">1. Name one producer in a food chain.<div className="paper-line" /><div className="paper-answer">grass</div></div>
                <div className="paper-question active">2. Why do plants need sunlight?<div className="paper-line" /><div className="paper-line" /></div>
                <div className="paper-question">3. Give one example of a decomposer.<div className="paper-line" /></div>
              </div>
              <div className="artifact-panel">
                <span className="micro-label">QUESTION 2 OF 3</span>
                <h2>Why do plants need sunlight?</h2>
                <span className="field-label">FINAL ANSWER</span>
                <div className="artifact-input">Plants use sunlight to make food.</div>
                <div className="artifact-status"><Check size={14} /> Ready for review</div>
                <div className="artifact-cta">Review answer <ArrowRight size={14} /></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="dark-band" id="how-it-works">
        <div className="page-width dark-grid">
          <div><p className="eyebrow">The safe sequence</p><h2>Less typing. More certainty.</h2></div>
          <div className="sequence">
            <div><strong>01</strong><p>Upload a supported worksheet.</p></div>
            <div><strong>02</strong><p>Talk, dictate, or type a final answer.</p></div>
            <div><strong>03</strong><p>Review the exact text and placement.</p></div>
            <div><strong>04</strong><p>Export a new PDF when every answer is committed.</p></div>
          </div>
        </div>
      </section>

      <section className="supported page-width" id="supported">
        <div><p className="eyebrow">Supported in V1</p><h2>Short-answer PDFs with one clear place to respond.</h2></div>
        <div className="supported-list">
          <p><Check size={15} /> Selectable text</p>
          <p><Check size={15} /> Sequential questions</p>
          <p><Check size={15} /> One answer area directly below each question</p>
          <p><X size={15} /> Scans, multiple choice, tables, and drawings stay out</p>
        </div>
      </section>

      <footer className="marketing-footer page-width">
        <Wordmark />
        <span>Claros keeps the source page immutable until you choose Export.</span>
        <Link to="/app">Open workspace <ArrowRight size={14} /></Link>
      </footer>
    </main>
  );
}

function WorkspaceFallback() {
  return <main className="route-loading" role="status">Opening workspace…</main>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<Suspense fallback={<WorkspaceFallback />}><Workspace /></Suspense>} />
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}
