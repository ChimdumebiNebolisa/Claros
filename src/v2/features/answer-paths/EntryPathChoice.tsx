import {
  ArrowRight,
  Eye,
  Lightbulb as Lightbulb02,
  Mic as Microphone01,
} from "lucide-react";
import { Button } from "@/v2/ui/Button";
import type { Question } from "../../domain/contracts";
import { QuestionHeader } from "./QuestionHeader";
import styles from "./answer-paths.module.css";

export type EntryPathChoiceProps = {
  question: Question;
  totalQuestions: number;
  onChooseDirect: () => void;
  onChooseGuided: () => void;
  onTypeInstead: () => void;
  onViewWorksheet?: () => void;
};

export function EntryPathChoice({
  question,
  totalQuestions,
  onChooseDirect,
  onChooseGuided,
  onTypeInstead,
  onViewWorksheet,
}: EntryPathChoiceProps) {
  return (
    <section className={styles.flow} aria-label="Choose how to answer">
      <QuestionHeader question={question} totalQuestions={totalQuestions} />

      <div className={styles.pathGrid}>
        <article className={styles.pathCard}>
          <span
            className="grid size-11 place-items-center rounded-lg bg-[var(--claros-blue-mist)] text-[var(--claros-blue-dark)]"
            aria-hidden="true"
          >
            <Microphone01 className="size-5" />
          </span>
          <div className={styles.pathCopy}>
            <h2>Say my answer</h2>
            <p>Speak or type what you already know.</p>
          </div>
          <Button
            color="link-color"
            size="lg"
            iconTrailing={ArrowRight}
            onPress={onChooseDirect}
            className={styles.pathAction}
          >
            Start answering
          </Button>
        </article>

        <article className={styles.pathCard}>
          <span
            className="grid size-11 place-items-center rounded-lg bg-[var(--claros-blue-mist)] text-[var(--claros-blue-dark)]"
            aria-hidden="true"
          >
            <Lightbulb02 className="size-5" />
          </span>
          <div className={styles.pathCopy}>
            <h2>Help me think it through</h2>
            <p>Work through the question with Claros, one step at a time.</p>
          </div>
          <Button
            color="link-color"
            size="lg"
            iconTrailing={ArrowRight}
            onPress={onChooseGuided}
            className={styles.pathAction}
          >
            Start a guided conversation
          </Button>
        </article>
      </div>

      <div className={styles.utilityActions} aria-label="Other ways to begin">
        <Button
          color="secondary"
          size="lg"
          onPress={onTypeInstead}
          className={styles.minimumTarget}
        >
          Type instead
        </Button>
        {onViewWorksheet ? (
          <Button
            color="link-gray"
            size="lg"
            iconLeading={Eye}
            onPress={onViewWorksheet}
            className={styles.minimumTarget}
          >
            View worksheet
          </Button>
        ) : null}
      </div>
    </section>
  );
}
