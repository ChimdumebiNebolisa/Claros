import type { Question } from "../../domain/contracts";

export type QuestionHeaderProps = {
  question: Question;
  totalQuestions: number;
};

export function QuestionHeader({
  question,
  totalQuestions,
}: QuestionHeaderProps) {
  return (
    <header className="border-l-2 border-[var(--claros-blue)] pl-5">
      <p className="m-0 text-xs font-bold uppercase tracking-[0.15em] text-[var(--claros-blue-dark)]">
        Question {question.index} of {totalQuestions}
      </p>
      <h1
        className="mt-3 max-w-[780px] text-[clamp(1.55rem,3vw,2rem)] font-semibold leading-[1.25] tracking-[-0.035em] text-[var(--claros-ink)] outline-none"
        tabIndex={-1}
      >
        {question.prompt}
      </h1>
      {question.instruction ? (
        <p className="mt-3 max-w-[720px] text-[15px] leading-6 text-[var(--claros-muted)]">
          {question.instruction}
        </p>
      ) : null}
    </header>
  );
}
