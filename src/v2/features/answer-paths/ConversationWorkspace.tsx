import { ArrowRight, Send, WandSparkles } from "lucide-react";
import { motion } from "motion/react";
import { useId, useRef, type ReactNode } from "react";
import { Button } from "@/v2/ui/Button";
import { Textarea } from "@/v2/ui/Textarea";
import type {
  ConversationTurn as ConversationTurnType,
  CaptureState,
  Question,
  VoiceState,
} from "../../domain/contracts";
import { QuestionHeader } from "./QuestionHeader";
import {
  VoiceStateControl,
  type VoiceStateControlProps,
} from "./VoiceStateControl";

export type ConversationWorkspaceProps = {
  question: Question;
  totalQuestions: number;
  turns: readonly ConversationTurnType[];
  message: string;
  candidateText: string;
  voiceState: VoiceState;
  captureState?: CaptureState;
  muted?: boolean;
  onMessageChange: (value: string) => void;
  onSendMessage: () => void;
  onCandidateChange: (value: string) => void;
  onMakeClearer: () => void;
  onReview: () => void;
  reviewContent?: ReactNode;
} & Pick<
  VoiceStateControlProps,
  | "onStart"
  | "onStop"
  | "onRetry"
  | "onContinueByTyping"
  | "onInterrupt"
  | "onToggleMute"
>;

function ConversationTurn({ turn }: { turn: ConversationTurnType }) {
  const isStudent = turn.speaker === "student";
  return (
    <li
      className={`grid max-w-[88%] gap-1 ${isStudent ? "self-end justify-items-end" : "self-start"}`}
    >
      <p className="m-0 px-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--claros-muted)]">
        {isStudent ? "You" : "Claros"}
      </p>
      <p
        className={`m-0 rounded-[14px] px-4 py-3 text-[15px] leading-6 ${isStudent ? "rounded-br-[4px] bg-[var(--claros-ink)] text-white" : "rounded-bl-[4px] bg-[var(--claros-blue-soft)] text-[var(--claros-ink)]"}`}
      >
        {turn.text}
      </p>
    </li>
  );
}

function ConversationHistory({
  turns,
}: {
  turns: readonly ConversationTurnType[];
}) {
  const collapsedTurns = turns.length > 6 ? turns.slice(0, -5) : [];
  const visibleTurns = turns.length > 6 ? turns.slice(-5) : turns;
  return (
    <div
      className="min-h-[170px] bg-white px-4 py-5 sm:px-5"
      role="region"
      aria-label="Conversation with Claros"
    >
      {collapsedTurns.length ? (
        <details className="mb-4 border-b border-[var(--claros-line)] pb-3 text-sm text-[var(--claros-muted)]">
          <summary className="min-h-11 cursor-pointer py-3 font-semibold">
            Show {collapsedTurns.length} earlier turns
          </summary>
          <ol className="flex list-none flex-col gap-3 p-0">
            {collapsedTurns.map((turn) => (
              <ConversationTurn key={turn.id} turn={turn} />
            ))}
          </ol>
        </details>
      ) : null}
      <ol
        className="flex list-none flex-col gap-4 p-0"
        aria-live="polite"
        aria-relevant="additions"
      >
        {visibleTurns.map((turn) => (
          <ConversationTurn key={turn.id} turn={turn} />
        ))}
      </ol>
    </div>
  );
}

export function ConversationWorkspace({
  question,
  totalQuestions,
  turns,
  message,
  candidateText,
  voiceState,
  captureState,
  muted,
  onMessageChange,
  onSendMessage,
  onCandidateChange,
  onMakeClearer,
  onReview,
  reviewContent,
  onStart,
  onStop,
  onRetry,
  onContinueByTyping,
  onInterrupt,
  onToggleMute,
}: ConversationWorkspaceProps) {
  const messageHelpId = useId();
  const candidateHelpId = useId();
  const messageRef = useRef<HTMLTextAreaElement>(null);
  const candidateRef = useRef<HTMLTextAreaElement>(null);
  const hasMessage = /\S/u.test(message);
  const hasCandidate = /\S/u.test(candidateText);

  if (reviewContent) {
    return (
      <section
        className="grid w-full max-w-[820px] gap-7"
        aria-label="Conversation workspace"
      >
        <QuestionHeader question={question} totalQuestions={totalQuestions} />
        <div className="overflow-hidden rounded-[10px] border border-[var(--claros-line)] bg-white">
          <VoiceStateControl
            state={voiceState}
            captureState={captureState}
            muted={muted}
            onStart={onStart}
            onStop={onStop}
            onRetry={onRetry}
            onContinueByTyping={() => {
              onContinueByTyping?.();
              messageRef.current?.focus();
            }}
            onInterrupt={onInterrupt}
            onToggleMute={onToggleMute}
          />
        </div>
        {reviewContent}
        {turns.length ? (
          <details className="rounded-[10px] border border-[var(--claros-line)] bg-white">
            <summary className="min-h-11 cursor-pointer px-4 py-3 text-sm font-semibold text-[var(--claros-muted)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--claros-blue)]">
              Conversation for this question
            </summary>
            <div className="border-t border-[var(--claros-line)]">
              <ConversationHistory turns={turns} />
            </div>
          </details>
        ) : null}
      </section>
    );
  }

  return (
    <section
      className="grid w-full max-w-[820px] gap-7"
      aria-label="Conversation workspace"
    >
      <QuestionHeader question={question} totalQuestions={totalQuestions} />
      <div className="overflow-hidden rounded-[16px] border border-[var(--claros-line-strong)] bg-white shadow-[0_1px_2px_rgba(17,32,51,.04),0_12px_40px_rgba(17,32,51,.06)]">
        <ConversationHistory turns={turns} />
        <VoiceStateControl
          state={voiceState}
          captureState={captureState}
          muted={muted}
          onStart={onStart}
          onStop={onStop}
          onRetry={onRetry}
          onContinueByTyping={() => {
            onContinueByTyping?.();
            messageRef.current?.focus();
          }}
          onInterrupt={onInterrupt}
          onToggleMute={onToggleMute}
        />
        <div className="relative bg-[var(--claros-canvas)] p-3">
          <p id={messageHelpId} className="sr-only">
            Dictate an answer, ask for help, request a revision, or type what
            you want to say.
          </p>
          <Textarea
            aria-label="Message Claros"
            aria-describedby={messageHelpId}
            value={message}
            onChange={onMessageChange}
            textAreaRef={messageRef}
            rows={2}
            placeholder="Say or type what you’re thinking…"
            className="min-h-[82px] resize-none border-0 bg-white pb-12 pr-14 shadow-[0_1px_3px_rgba(17,32,51,.08)] focus:ring-2"
            onKeyDown={(event) => {
              if (
                (event.metaKey || event.ctrlKey) &&
                event.key === "Enter" &&
                hasMessage
              )
                onSendMessage();
            }}
          />
          <Button
            color="primary"
            size="sm"
            iconLeading={Send}
            onPress={onSendMessage}
            isDisabled={!hasMessage}
            className="absolute bottom-6 right-6 size-10 min-h-10 rounded-lg p-0"
            aria-label="Send to Claros"
          />
          <span className="pointer-events-none absolute bottom-7 left-7 text-[11px] font-medium text-[var(--claros-muted)]">
            Ctrl/⌘ + Enter to send
          </span>
        </div>
      </div>

      <>
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className={`border-l-2 pl-5 ${hasCandidate ? "border-[var(--claros-blue)]" : "border-[var(--claros-line-strong)]"}`}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="m-0 text-xs font-bold uppercase tracking-[0.15em] text-[var(--claros-blue-dark)]">
              Your answer
            </p>
            <span className="text-xs text-[var(--claros-muted)]">
              Separate from the conversation
            </span>
          </div>
          <p
            id={candidateHelpId}
            className="mt-2 text-sm leading-6 text-[var(--claros-muted)]"
          >
            Only this editable wording can move to exact review.
          </p>
          <Textarea
            aria-label="Proposed answer"
            aria-describedby={candidateHelpId}
            value={candidateText}
            onChange={onCandidateChange}
            textAreaRef={candidateRef}
            rows={5}
            placeholder="Your answer will appear here—or type it directly."
            className={`mt-3 min-h-[132px] text-[17px] leading-7 ${hasCandidate ? "border-[var(--claros-blue)] bg-white shadow-[0_1px_2px_rgba(17,32,51,.04)]" : "bg-[var(--claros-canvas)]"}`}
          />
        </motion.div>
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          {hasCandidate ? (
            <Button
              color="secondary"
              size="lg"
              iconLeading={WandSparkles}
              onPress={onMakeClearer}
            >
              Make it clearer
            </Button>
          ) : null}
          <Button
            color="primary"
            size="lg"
            iconTrailing={ArrowRight}
            onPress={onReview}
            isDisabled={!hasCandidate}
          >
            Review answer
          </Button>
        </div>
      </>
    </section>
  );
}
