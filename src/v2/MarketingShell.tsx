import {
  ArrowRight,
  Check,
  FileCheck2,
  Menu,
  MessageCircleMore,
  Mic2,
  PenLine,
  X,
} from "lucide-react";
import { Dialog } from "radix-ui";
import { Link } from "react-router-dom";
import { Brand } from "./Brand";

const steps = [
  {
    icon: Mic2,
    title: "Talk naturally",
    copy: "Say the answer you know, or explain where you’re stuck.",
  },
  {
    icon: MessageCircleMore,
    title: "Work it out",
    copy: "Claros helps with the question while keeping your words in view.",
  },
  {
    icon: PenLine,
    title: "Approve your words",
    copy: "Edit and review the exact answer before anything is added.",
  },
  {
    icon: FileCheck2,
    title: "Get the completed PDF",
    copy: "Your approved answer is placed into a new copy of the worksheet.",
  },
] as const;

const guarantees = [
  "Your words stay editable",
  "Nothing is added without approval",
  "Your original PDF stays intact",
] as const;

function PrimaryLink({ children = "Try Claros" }: { children?: string }) {
  return (
    <Link
      to="/app"
      className="inline-flex min-h-12 items-center justify-center gap-2 rounded-[10px] bg-[var(--claros-blue)] px-5 text-[15px] font-semibold text-white shadow-[0_1px_2px_rgba(17,32,51,.14),0_8px_24px_rgba(21,94,239,.18)] outline-none transition hover:bg-[var(--claros-blue-dark)] focus-visible:ring-2 focus-visible:ring-[var(--claros-blue)] focus-visible:ring-offset-2 active:translate-y-px"
    >
      {children}
      <ArrowRight className="size-4" aria-hidden="true" />
    </Link>
  );
}

function MobileNavigation() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex size-11 items-center justify-center rounded-lg border border-[var(--claros-line)] bg-white text-[var(--claros-ink)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--claros-blue)] md:hidden"
          aria-label="Open navigation"
        >
          <Menu className="size-5" aria-hidden="true" />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[rgba(17,32,51,.28)] backdrop-blur-[2px]" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 w-[min(88vw,360px)] border-l border-[var(--claros-line)] bg-white p-6 shadow-[-24px_0_70px_rgba(17,32,51,.14)] outline-none md:hidden">
          <div className="flex items-center justify-between">
            <Dialog.Title className="font-display text-2xl text-[var(--claros-ink)]">
              Claros
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="inline-flex size-11 items-center justify-center rounded-lg text-[var(--claros-muted)] outline-none hover:bg-[var(--claros-soft)] focus-visible:ring-2 focus-visible:ring-[var(--claros-blue)]"
                aria-label="Close navigation"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            </Dialog.Close>
          </div>
          <nav className="mt-10 grid gap-2" aria-label="Mobile navigation">
            <Dialog.Close asChild>
              <a
                className="rounded-lg px-3 py-3 text-lg font-medium text-[var(--claros-ink)] hover:bg-[var(--claros-soft)]"
                href="#how-it-works"
              >
                How it works
              </a>
            </Dialog.Close>
            <Dialog.Close asChild>
              <a
                className="rounded-lg px-3 py-3 text-lg font-medium text-[var(--claros-ink)] hover:bg-[var(--claros-soft)]"
                href="#accessibility"
              >
                Accessibility
              </a>
            </Dialog.Close>
            <div className="mt-4">
              <PrimaryLink />
            </div>
          </nav>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function MarketingShell() {
  return (
    <div className="min-h-screen overflow-hidden bg-[var(--claros-paper)] text-[var(--claros-ink)]">
      <header className="border-b border-[color-mix(in_srgb,var(--claros-line)_78%,transparent)]">
        <div className="mx-auto flex h-[72px] max-w-[1240px] items-center justify-between px-5 sm:px-8">
          <Brand />
          <nav
            className="hidden items-center gap-8 md:flex"
            aria-label="Primary navigation"
          >
            <a
              className="text-sm font-medium text-[var(--claros-muted)] transition hover:text-[var(--claros-ink)]"
              href="#how-it-works"
            >
              How it works
            </a>
            <a
              className="text-sm font-medium text-[var(--claros-muted)] transition hover:text-[var(--claros-ink)]"
              href="#accessibility"
            >
              Accessibility
            </a>
            <PrimaryLink />
          </nav>
          <MobileNavigation />
        </div>
      </header>

      <main>
        <section className="relative isolate px-5 pb-24 pt-20 text-center sm:px-8 sm:pb-32 sm:pt-28 lg:pb-36 lg:pt-36">
          <div
            className="pointer-events-none absolute inset-x-0 top-[-220px] -z-10 mx-auto h-[520px] max-w-[900px] rounded-full bg-[radial-gradient(circle,rgba(21,94,239,.09),transparent_68%)] blur-2xl"
            aria-hidden="true"
          />
          <div className="mx-auto max-w-[940px]">
            <p className="text-[12px] font-bold uppercase tracking-[0.18em] text-[var(--claros-blue-dark)] sm:text-[13px]">
              Built for students who find typing difficult
            </p>
            <h1
              aria-label="Think it. Say it. Put it on the page."
              className="mt-7 font-display text-[clamp(3.6rem,8.3vw,7.5rem)] leading-[0.87] tracking-[-0.045em] text-[var(--claros-ink)]"
            >
              Think it.{" "}
              <span className="text-[var(--claros-blue)]">Say it.</span>
              <span className="mt-2 block">Put it on the page.</span>
            </h1>
            <p className="mx-auto mt-8 max-w-[660px] text-[17px] leading-7 text-[var(--claros-muted)] sm:text-xl sm:leading-8">
              Talk through a question or say the answer you already know. Review
              the exact wording, approve it, and Claros places it into your PDF.
            </p>
            <div className="mt-9 flex justify-center">
              <PrimaryLink />
            </div>
            <p className="mt-5 text-sm font-medium text-[var(--claros-muted)]">
              Nothing reaches your worksheet until you approve it.
            </p>
          </div>
        </section>

        <section
          id="how-it-works"
          className="border-y border-[var(--claros-line)] bg-[var(--claros-canvas)] px-5 py-20 sm:px-8 sm:py-24"
        >
          <div className="mx-auto max-w-[1180px]">
            <div className="mx-auto max-w-[620px] text-center">
              <p className="text-[12px] font-bold uppercase tracking-[0.17em] text-[var(--claros-blue-dark)]">
                From thought to worksheet
              </p>
              <h2 className="mt-4 font-display text-5xl leading-[0.96] tracking-[-0.03em] sm:text-6xl">
                Just talk to Claros.
              </h2>
              <p className="mt-5 text-base leading-7 text-[var(--claros-muted)] sm:text-lg">
                One conversation meets you where you are, then keeps the final
                wording separate until you approve it.
              </p>
            </div>
            <ol className="relative mt-14 grid gap-0 border-t border-[var(--claros-line-strong)] md:grid-cols-4">
              {steps.map(({ icon: Icon, title, copy }, index) => (
                <li
                  key={title}
                  className="relative border-b border-[var(--claros-line)] py-7 md:border-b-0 md:border-r md:px-6 md:py-8 first:md:pl-0 last:md:border-r-0 last:md:pr-0"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold tracking-[0.12em] text-[var(--claros-blue-dark)]">
                      0{index + 1}
                    </span>
                    <Icon
                      className="size-5 text-[var(--claros-blue)]"
                      strokeWidth={1.75}
                      aria-hidden="true"
                    />
                  </div>
                  <h3 className="mt-8 text-[17px] font-semibold tracking-[-0.015em]">
                    {title}
                  </h3>
                  <p className="mt-2 max-w-[240px] text-sm leading-6 text-[var(--claros-muted)]">
                    {copy}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="bg-[var(--claros-night)] px-5 py-20 text-white sm:px-8 sm:py-24">
          <div className="mx-auto grid max-w-[1180px] gap-12 lg:grid-cols-[1fr_.8fr] lg:items-end">
            <div>
              <p className="text-[12px] font-bold uppercase tracking-[0.17em] text-[#9fc1ff]">
                Student control
              </p>
              <h2 className="mt-5 max-w-[680px] font-display text-5xl leading-[0.96] tracking-[-0.03em] sm:text-6xl">
                Your answer stays yours.
              </h2>
              <p className="mt-6 max-w-[620px] text-base leading-7 text-[#bdc8da] sm:text-lg">
                Conversation helps you think. A separate editable draft holds
                the words that can become your answer.
              </p>
            </div>
            <ul className="grid gap-4 border-t border-white/15 pt-6">
              {guarantees.map((guarantee) => (
                <li
                  key={guarantee}
                  className="flex items-center gap-3 text-[15px] font-medium"
                >
                  <span className="grid size-6 place-items-center rounded-full bg-[#164ea5] text-[#dbe9ff]">
                    <Check
                      className="size-3.5"
                      strokeWidth={2.5}
                      aria-hidden="true"
                    />
                  </span>
                  {guarantee}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="accessibility" className="px-5 py-20 sm:px-8 sm:py-24">
          <div className="mx-auto grid max-w-[1180px] gap-12 lg:grid-cols-[1fr_.72fr] lg:gap-24">
            <div>
              <p className="text-[12px] font-bold uppercase tracking-[0.17em] text-[var(--claros-blue-dark)]">
                Accessibility
              </p>
              <h2 className="mt-4 font-display text-5xl leading-[0.96] tracking-[-0.03em] sm:text-6xl">
                Voice-first, never voice-only.
              </h2>
              <p className="mt-6 max-w-[680px] text-lg leading-8 text-[var(--claros-muted)]">
                Speak when typing is difficult. Type when that’s easier. Switch
                between them without losing your place.
              </p>
            </div>
            <div className="border-l-2 border-[var(--claros-blue)] pl-6 lg:self-end">
              <h3 className="text-base font-semibold">
                Works with text-based short-answer PDFs
              </h3>
              <p className="mt-3 text-sm leading-6 text-[var(--claros-muted)]">
                Up to 8 pages and 40 questions. Scanned worksheets aren’t
                supported yet. If wording cannot fit safely beside a question,
                Claros uses an attached answer page.
              </p>
            </div>
          </div>
        </section>

        <section className="px-5 pb-20 sm:px-8 sm:pb-24">
          <div className="mx-auto flex max-w-[1180px] flex-col items-start justify-between gap-8 border-t border-[var(--claros-line-strong)] pt-12 sm:flex-row sm:items-end">
            <h2 className="max-w-[650px] font-display text-5xl leading-[0.98] tracking-[-0.03em] sm:text-6xl">
              Have a worksheet to finish?
            </h2>
            <PrimaryLink>Upload it and start talking</PrimaryLink>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--claros-line)] px-5 py-7 sm:px-8">
        <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-6 text-sm text-[var(--claros-muted)]">
          <Brand />
          <span>Speak, review, approve.</span>
        </div>
      </footer>
    </div>
  );
}
