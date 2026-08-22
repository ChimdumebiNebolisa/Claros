import { createActor } from "xstate";
import { describe, expect, it } from "vitest";
import { workspaceMachine } from "../src/domain/workspace-machine";

const assignment = {
  id: "a1",
  worksheet: {
    id: "w1",
    title: "Sample",
    pageCount: 1,
    sourceHash: "a".repeat(64),
    questions: [{ id: "q1", index: 1, prompt: "Question?", pageIndex: 0, answerRegion: { id: "r1", pageIndex: 0, bounds: { x: 0, y: 0, width: 10, height: 54 } } }],
  },
  committedAnswers: [],
  activeQuestionId: "q1",
};

describe("workspace state model", () => {
  it("keeps review and commit as separate states", () => {
    const actor = createActor(workspaceMachine).start();
    actor.send({ type: "LOAD" });
    actor.send({ type: "LOADED", assignment });
    actor.send({ type: "DRAFT_CHANGED", value: "Exact answer" });
    actor.send({ type: "REVIEW" });
    expect(actor.getSnapshot().value).toBe("review");
    actor.send({ type: "COMMIT" });
    expect(actor.getSnapshot().value).toBe("committing");
    actor.stop();
  });
});
