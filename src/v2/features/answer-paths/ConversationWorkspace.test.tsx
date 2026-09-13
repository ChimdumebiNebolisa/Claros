// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationWorkspace } from "./ConversationWorkspace";

afterEach(cleanup);

describe("ConversationWorkspace exact review", () => {
  it("places exact review before the secondary conversation transcript", () => {
    render(
      <ConversationWorkspace
        question={{
          id: "question-1",
          index: 0,
          prompt: "Why do plants need sunlight?",
          instruction: "Answer in one sentence.",
          pageNumber: 1,
          placement: "inline",
        }}
        totalQuestions={2}
        turns={[
          {
            id: "turn-1",
            speaker: "student",
            text: "They use it to make food.",
            questionId: "question-1",
          },
        ]}
        message=""
        candidateText="They use sunlight to make food."
        voiceState="ready"
        captureState="inactive"
        muted={false}
        onMessageChange={vi.fn()}
        onSendMessage={vi.fn()}
        onCandidateChange={vi.fn()}
        onMakeClearer={vi.fn()}
        onReview={vi.fn()}
        onStart={vi.fn()}
        onStop={vi.fn()}
        onRetry={vi.fn()}
        onContinueByTyping={vi.fn()}
        onInterrupt={vi.fn()}
        onToggleMute={vi.fn()}
        reviewContent={
          <section data-testid="exact-review">Exact review</section>
        }
      />,
    );

    const review = screen.getByTestId("exact-review");
    const transcriptSummary = screen.getByText(
      "Conversation for this question",
    );

    expect(
      review.compareDocumentPosition(transcriptSummary) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
