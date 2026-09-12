import { ArrowRight, MagicWand02, Send01 } from "@untitledui/icons";
import { useId, useRef, type ReactNode } from "react";
import { Button } from "@/components/base/buttons/button";
import { TextArea } from "@/components/base/textarea/textarea";
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
import styles from "./answer-paths.module.css";

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
  return (
    <li
      className={
        turn.speaker === "student" ? styles.studentTurn : styles.clarosTurn
      }
    >
      <p className={styles.turnSpeaker}>
        {turn.speaker === "student" ? "You" : "Claros"}
      </p>
      <p>{turn.text}</p>
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
      className={styles.conversation}
      role="region"
      aria-label="Conversation with Claros"
    >
      {collapsedTurns.length ? (
        <details className={styles.earlierTurns}>
          <summary>Show {collapsedTurns.length} earlier turns</summary>
          <ol className={styles.turnList}>
            {collapsedTurns.map((turn) => (
              <ConversationTurn key={turn.id} turn={turn} />
            ))}
          </ol>
        </details>
      ) : null}
      <ol
        className={styles.turnList}
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

  return (
    <section className={styles.flow} aria-label="Conversation workspace">
      <QuestionHeader question={question} totalQuestions={totalQuestions} />
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

      {reviewContent ? (
        reviewContent
      ) : (
        <>
          <div className={styles.answerEditor}>
            <p className={styles.provenance}>Talk with Claros</p>
            <p id={messageHelpId} className={styles.editorHint}>
              Dictate an answer, ask for help, request a revision, or type what
              you want to say. Claros will clarify ambiguous intent.
            </p>
            <TextArea
              aria-label="Message Claros"
              aria-describedby={messageHelpId}
              value={message}
              onChange={onMessageChange}
              textAreaRef={messageRef}
              rows={3}
              placeholder="Type a message or answer…"
              textAreaClassName={styles.answerTextArea}
            />
            <div className={styles.answerActions}>
              <Button
                color="secondary"
                size="lg"
                iconTrailing={Send01}
                onPress={onSendMessage}
                isDisabled={!hasMessage}
                className={styles.minimumTarget}
              >
                Send to Claros
              </Button>
            </div>
          </div>

          <div className={styles.answerEditor}>
            <p className={styles.provenance}>Proposed answer</p>
            <p id={candidateHelpId} className={styles.editorHint}>
              Only this editable text can move to exact review. Conversation
              alone never writes to the worksheet.
            </p>
            <TextArea
              aria-label="Proposed answer"
              aria-describedby={candidateHelpId}
              value={candidateText}
              onChange={onCandidateChange}
              textAreaRef={candidateRef}
              rows={5}
              placeholder="Your intended answer will appear here, or you can type it directly."
              textAreaClassName={styles.answerTextArea}
            />
          </div>

          <div className={styles.answerActions}>
            {hasCandidate ? (
              <Button
                color="secondary"
                size="lg"
                iconLeading={MagicWand02}
                onPress={onMakeClearer}
                className={styles.minimumTarget}
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
              className={styles.minimumTarget}
            >
              Review answer
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
