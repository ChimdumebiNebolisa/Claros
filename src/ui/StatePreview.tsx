import type { ReactNode } from "react";

export type AnswerState = "draft" | "review" | "blocked" | "committed" | "unsupported" | "expired";

const stateCopy: Record<AnswerState, { label: string; description: string }> = {
  draft: { label: "Draft", description: "Nothing is committed yet." },
  review: { label: "Review", description: "Check the exact answer before adding it." },
  blocked: { label: "Blocked placement", description: "This answer needs a safe placement decision." },
  committed: { label: "Committed", description: "The answer is ready in the browser preview." },
  unsupported: { label: "Unsupported worksheet", description: "This source is outside the supported contract." },
  expired: { label: "Session expired", description: "Start again to continue safely." },
};

export function StatePreview({ state, children }: { state: AnswerState; children?: ReactNode }) {
  const copy = stateCopy[state];
  return (
    <article className={`state-preview state-preview-${state}`} aria-label={`${copy.label} state`}>
      <span className="field-label">{copy.label}</span>
      <p>{copy.description}</p>
      {children}
    </article>
  );
}
