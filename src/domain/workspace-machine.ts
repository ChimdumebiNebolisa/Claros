import { assign, createMachine } from "xstate";
import type { Assignment, PlacementPlan } from "./contracts";

export type WorkspaceContext = {
  assignment: Assignment | null;
  draft: string;
  plan: PlacementPlan | null;
  error: string | null;
};

export const workspaceMachine = createMachine({
  id: "claros-workspace",
  types: {} as { context: WorkspaceContext; events:
    | { type: "LOAD" }
    | { type: "LOADED"; assignment: Assignment }
    | { type: "FAILED"; message: string }
    | { type: "DRAFT_CHANGED"; value: string }
    | { type: "REVIEW" }
    | { type: "PLAN_READY"; plan: PlacementPlan }
    | { type: "EDIT" }
    | { type: "COMMIT" }
    | { type: "COMMITTED"; assignment: Assignment }
    | { type: "NEXT" }
    | { type: "EXPORT" }
    | { type: "EXPORTED" }
  },
  context: { assignment: null, draft: "", plan: null, error: null },
  initial: "upload",
  states: {
    upload: { on: { LOAD: "analyzing" } },
    analyzing: {
      on: {
        LOADED: { target: "working", actions: assign({ assignment: ({ event }) => event.assignment, draft: "", plan: null, error: null }) },
        FAILED: { target: "unsupported", actions: assign({ error: ({ event }) => event.message }) },
      },
    },
    unsupported: { on: { LOAD: "analyzing" } },
    working: {
      on: {
        DRAFT_CHANGED: { actions: assign({ draft: ({ event }) => event.value, plan: null }) },
        REVIEW: "review",
        NEXT: { actions: assign({ draft: "", plan: null }) },
        EXPORT: "exporting",
        FAILED: { actions: assign({ error: ({ event }) => event.message }) },
      },
    },
    review: {
      on: {
        PLAN_READY: { actions: assign({ plan: ({ event }) => event.plan, error: null }) },
        FAILED: { target: "working", actions: assign({ error: ({ event }) => event.message }) },
        EDIT: { target: "working", actions: assign({ plan: null }) },
        COMMIT: "committing",
      },
    },
    committing: {
      on: {
        COMMITTED: { target: "committed", actions: assign({ assignment: ({ event }) => event.assignment, plan: null }) },
        FAILED: { target: "review", actions: assign({ error: ({ event }) => event.message }) },
      },
    },
    committed: {
      on: {
        EDIT: { target: "working", actions: assign({ draft: ({ context }) => context.plan?.answerText ?? "", plan: null }) },
        NEXT: { target: "working", actions: assign({ draft: "", plan: null }) },
        EXPORT: "exporting",
      },
    },
    exporting: {
      on: {
        EXPORTED: "complete",
        FAILED: { target: "working", actions: assign({ error: ({ event }) => event.message }) },
      },
    },
    complete: { on: { EXPORT: "exporting" } },
  },
});
