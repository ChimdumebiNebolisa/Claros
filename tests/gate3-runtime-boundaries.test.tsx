// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AppProviders } from "../src/v2/AppProviders";
import RootApp from "../src/v2/RootApp";
import type { RealtimeListener } from "../src/v2/realtime/realtime-adapter";

const realtimeMocks = vi.hoisted(() => ({
  load: vi.fn(),
  loadOpenAI: vi.fn(),
}));

vi.mock("../src/v2/realtime/loadRealtime", () => ({
  loadRealtimeAdapter: realtimeMocks.load,
}));

vi.mock("../src/v2/realtime/loadOpenAIRealtime", () => ({
  loadOpenAIRealtimeAdapter: realtimeMocks.loadOpenAI,
}));

vi.mock("../src/v2/document/DocumentCrop", () => ({
  default: () => <div data-testid="document-crop" />,
}));

vi.mock("../src/v2/document/WorksheetDialog", () => ({
  default: () => <div role="dialog" aria-label="Worksheet" />,
}));

// Match the established route-suite pattern: resolve the production lazy
// boundary before assertions so these tests measure API hydration, not host
// module-import speed.
await import("../src/v2/WorkspaceShell");

const assignment = {
  assignment_id: "asgn_runtime",
  version: 3,
  status: "ready",
  title: "Runtime worksheet",
  source: {
    filename: "runtime.pdf",
    size_bytes: 1024,
    sha256: "b".repeat(64),
    page_count: 1,
  },
  question_count: 1,
  placement_summary: { inline_possible: 0, appendix_only: 1 },
  warnings: [],
  questions: [
    {
      question_id: "q_runtime",
      index: 1,
      prompt: "What is the runtime question?",
      instruction: null,
      page_number: 1,
      placement_capability: "appendix_only",
      candidate: null,
      wording_comparison: null,
      confirmed_answer: null,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  realtimeMocks.load.mockReset();
  realtimeMocks.loadOpenAI.mockReset();
});

describe("Gate 3 runtime boundaries", () => {
  it("polls a reload-safe analyzing assignment until it is ready", async () => {
    const analyzing = {
      ...assignment,
      status: "analyzing",
      question_count: 0,
      questions: [],
      source: { ...assignment.source, page_count: null },
    };
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        const payload = init?.method === "POST" ? analyzing : assignment;
        return new Response(JSON.stringify(payload), {
          status: init?.method === "POST" ? 201 : 200,
          headers: { "content-type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/app"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole(
        "button",
        { name: "Try the biology sample" },
        { timeout: 5_000 },
      ),
    );
    expect(
      await screen.findByRole(
        "heading",
        { name: "Your worksheet is ready." },
        { timeout: 3_000 },
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe(
      "/api/v2/assignments/asgn_runtime",
    );
  });

  it("loads the live adapter without loading the fixture Realtime adapter", async () => {
    const liveAdapter = {
      subscribe: vi.fn(() => vi.fn()),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(() => ({ id: "listen", command: "listen" })),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "What is the runtime question?",
      }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start speaking" }));

    await waitFor(() => expect(liveAdapter.startListening).toHaveBeenCalled());
    expect(liveAdapter.connect).toHaveBeenCalledWith(
      expect.objectContaining({
        assignmentId: "asgn_runtime",
        assignmentVersion: 3,
        questionId: "q_runtime",
        mode: "conversation",
        exactQuestion: "What is the runtime question?",
        microphone: true,
      }),
    );
    expect(realtimeMocks.loadOpenAI).toHaveBeenCalledOnce();
    expect(realtimeMocks.load).not.toHaveBeenCalled();
  });

  it("keeps Stop listening reachable while Claros is thinking or speaking", async () => {
    let listener: RealtimeListener | undefined;
    const liveAdapter = {
      subscribe: vi.fn((next: RealtimeListener) => {
        listener = next;
        return vi.fn();
      }),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(() => ({ id: "listen", command: "listen" })),
      stopListening: vi.fn(() => ({ id: "stop", command: "stop" })),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.click(screen.getByRole("button", { name: "Start speaking" }));
    await waitFor(() => expect(listener).toBeDefined());
    act(() => {
      listener?.({ id: "listening", type: "voice_state", state: "listening" });
      listener?.({ id: "thinking", type: "voice_state", state: "thinking" });
    });
    expect(
      screen.getByRole("button", { name: "Stop listening" }),
    ).toBeEnabled();

    act(() => {
      listener?.({ id: "speaking", type: "voice_state", state: "speaking" });
    });
    expect(
      screen.getByRole("button", { name: "Stop listening" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Interrupt Claros" }),
    ).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Stop listening" }));
    expect(liveAdapter.stopListening).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Start speaking" }),
    ).toBeEnabled();
  });

  it("reuses a healthy audio session when the student sends a typed turn", async () => {
    const liveAdapter = {
      subscribe: vi.fn(() => vi.fn()),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(() => ({ id: "listen", command: "listen" })),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.click(screen.getByRole("button", { name: "Start speaking" }));
    await user.type(
      screen.getByRole("textbox", { name: "Message Claros" }),
      "Can you explain one step?",
    );
    await user.click(screen.getByRole("button", { name: "Send to Claros" }));

    await waitFor(() =>
      expect(liveAdapter.sendTypedTurn).toHaveBeenCalledWith(
        "Can you explain one step?",
      ),
    );
    expect(liveAdapter.connect).toHaveBeenCalledOnce();
    expect(liveAdapter.destroy).not.toHaveBeenCalled();
    expect(liveAdapter.connect).toHaveBeenCalledWith(
      expect.objectContaining({ microphone: true }),
    );
  });

  it("offers typed recovery when the live adapter cannot load", async () => {
    realtimeMocks.loadOpenAI.mockRejectedValue(
      new Error("Realtime module unavailable"),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.click(screen.getByRole("button", { name: "Start speaking" }));

    expect(await screen.findByText("Connection lost")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Continue by typing" }),
    ).toBeEnabled();
    expect(realtimeMocks.load).not.toHaveBeenCalled();
  });

  it("posts direct voice candidates with bound Realtime provenance", async () => {
    let listener: RealtimeListener | undefined;
    const liveAdapter = {
      subscribe: vi.fn((next: RealtimeListener) => {
        listener = next;
        return vi.fn();
      }),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(() => ({ id: "listen", command: "listen" })),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    const candidate = {
      candidate_id: "cand_voice",
      candidate_version: 1,
      question_id: "q_runtime",
      text: "Plants use sunlight as energy.",
      origin: "student_normalized",
      attribution: "Your words",
      created_at: "2026-09-04T12:00:00Z",
    };
    let candidateRequest: Record<string, unknown> | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/candidates")) {
          candidateRequest = JSON.parse(String(init?.body)) as Record<
            string,
            unknown
          >;
          return new Response(JSON.stringify({ version: 4, candidate }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        if (url.endsWith("/review")) {
          return new Response(
            JSON.stringify({
              version: 4,
              question_id: "q_runtime",
              candidate,
              attribution: "Your words",
              review_token: "review_voice",
              expires_at: "2040-01-01T00:00:00Z",
              placement: "appendix",
              preview_context_url: "/context",
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          );
        }
        if (url.endsWith("/confirm")) {
          return new Response(
            JSON.stringify({
              version: 5,
              confirmation_id: "confirmation_voice",
              replayed: false,
              confirmed_answer: {
                question_id: "q_runtime",
                revision: 1,
                candidate_id: candidate.candidate_id,
                candidate_version: candidate.candidate_version,
                exact_text: candidate.text,
                origin: candidate.origin,
                attribution: "Your words",
                placement: "appendix",
                confirmed_at: "2026-09-04T12:01:00Z",
              },
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          );
        }
        return new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.click(screen.getByRole("button", { name: "Start speaking" }));
    await waitFor(() => expect(listener).toBeDefined());
    act(() => {
      listener?.({
        id: "voice_listening",
        type: "voice_state",
        state: "listening",
      });
      listener?.({
        id: "candidate_event",
        type: "candidate",
        text: candidate.text,
        input: "voice",
        normalization: "punctuation_only",
        sessionId: "sess_voice",
        sourceTurnIds: ["turn_voice_1"],
      });
    });
    await user.click(screen.getByRole("button", { name: "Review answer" }));
    await screen.findByRole("heading", { name: "Review your exact answer" });
    expect(
      screen.getByRole("button", { name: "Stop listening" }),
    ).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Hear it" }));
    expect(liveAdapter.hearExact).toHaveBeenCalledWith(candidate.text);
    expect(
      screen.getByRole("button", { name: "Use this exact answer" }),
    ).toBeEnabled();

    expect(candidateRequest).toMatchObject({
      origin: "student_normalized",
      interaction: {
        kind: "direct_voice",
        realtime_session_id: "sess_voice",
        source_turn_ids: ["turn_voice_1"],
        normalization: "punctuation_only",
      },
    });

    act(() => {
      listener?.({
        id: "casual_confirmation",
        type: "transcript",
        speaker: "student",
        text: "okay",
        final: true,
      });
    });
    expect(
      screen.getByRole("heading", { name: "Review your exact answer" }),
    ).toBeInTheDocument();

    act(() => {
      listener?.({
        id: "exact_confirmation",
        type: "transcript",
        speaker: "student",
        text: "Use this exact answer",
        final: true,
      });
    });
    expect(
      await screen.findByRole("heading", {
        name: "Answer added to the attached answer page.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Stop listening" }),
    ).toBeEnabled();
  });

  it("preserves a voice draft through microphone denial and finishes by typing", async () => {
    let listener: RealtimeListener | undefined;
    const liveAdapter = {
      subscribe: vi.fn((next: RealtimeListener) => {
        listener = next;
        return vi.fn();
      }),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(() => ({ id: "listen", command: "listen" })),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    const completedText =
      "Plants need sunlight because it supplies energy for photosynthesis.";
    const candidate = {
      candidate_id: "cand_typed_fallback",
      candidate_version: 1,
      question_id: "q_runtime",
      text: completedText,
      origin: "student_verbatim",
      attribution: "Your words",
      created_at: "2026-09-04T12:00:00Z",
    };
    const candidateRequests: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/candidates")) {
          candidateRequests.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return new Response(JSON.stringify({ version: 4, candidate }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        if (url.endsWith("/review")) {
          return new Response(
            JSON.stringify({
              version: 4,
              question_id: "q_runtime",
              candidate,
              attribution: "Your words",
              review_token: "review_typed_fallback",
              expires_at: "2040-01-01T00:00:00Z",
              placement: "appendix",
              preview_context_url: "/context",
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          );
        }
        return new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.click(screen.getByRole("button", { name: "Start speaking" }));
    await waitFor(() => expect(listener).toBeDefined());
    act(() => {
      listener?.({
        id: "partial_voice_candidate",
        type: "candidate",
        text: "Plants need sunlight because",
        input: "voice",
        normalization: "none",
        sessionId: "sess_denied",
        sourceTurnIds: ["turn_partial"],
      });
      listener?.({
        id: "microphone_denied",
        type: "error",
        code: "microphone_unavailable",
        message: "Microphone unavailable",
      });
    });

    const answer = screen.getByRole("textbox", { name: "Proposed answer" });
    expect(answer).toHaveValue("Plants need sunlight because");
    await user.click(
      screen.getByRole("button", { name: "Continue by typing" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Message Claros" }),
    ).toHaveFocus();
    await user.clear(answer);
    await user.type(answer, completedText);
    await user.click(screen.getByRole("button", { name: "Review answer" }));

    expect(
      await screen.findByRole("heading", { name: "Review your exact answer" }),
    ).toBeInTheDocument();
    expect(candidateRequests).toHaveLength(1);
    expect(candidateRequests[0]).toMatchObject({
      text: completedText,
      origin: "student_verbatim",
      interaction: { kind: "direct_typed" },
    });
  });

  it("keeps natural typed conversation microphone-free and posts typed provenance", async () => {
    let listener: RealtimeListener | undefined;
    const liveAdapter = {
      subscribe: vi.fn((next: RealtimeListener) => {
        listener = next;
        return vi.fn();
      }),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(() => ({
        sessionId: "sess_guided",
        sourceTurnIds: ["typed_final_1"],
        input: "typed",
        normalization: "none",
      })),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    const candidate = {
      candidate_id: "cand_guided",
      candidate_version: 1,
      question_id: "q_runtime",
      text: "Plants use sunlight to make food.",
      origin: "student_after_guidance",
      attribution: "Your words",
      created_at: "2026-09-04T12:00:00Z",
    };
    let candidateRequest: Record<string, unknown> | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/candidates")) {
          candidateRequest = JSON.parse(String(init?.body)) as Record<
            string,
            unknown
          >;
          return new Response(JSON.stringify({ version: 4, candidate }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        if (url.endsWith("/review")) {
          return new Response(
            JSON.stringify({
              version: 4,
              question_id: "q_runtime",
              candidate,
              attribution: "Your words",
              review_token: "review_guided",
              expires_at: "2040-01-01T00:00:00Z",
              placement: "appendix",
              preview_context_url: "/context",
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          );
        }
        return new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.type(
      screen.getByRole("textbox", { name: "Message Claros" }),
      "Light provides energy.",
    );
    await user.click(screen.getByRole("button", { name: "Send to Claros" }));
    await waitFor(() => expect(listener).toBeDefined());
    act(() => {
      listener?.({
        id: "speaking_event",
        type: "voice_state",
        state: "speaking",
      });
      listener?.({
        id: "reply_event",
        type: "transcript",
        speaker: "claros",
        text: "Now state your final answer.",
        final: true,
      });
    });
    expect(
      screen.getAllByText("Now state your final answer.").length,
    ).toBeGreaterThan(0);
    expect(candidateRequest).toBeUndefined();
    await user.type(
      screen.getByRole("textbox", { name: "Proposed answer" }),
      candidate.text,
    );
    await user.click(screen.getByRole("button", { name: "Review answer" }));
    await screen.findByRole("heading", { name: "Review your exact answer" });

    expect(liveAdapter.connect).toHaveBeenCalledWith(
      expect.objectContaining({ microphone: false, mode: "conversation" }),
    );
    expect(liveAdapter.startListening).not.toHaveBeenCalled();
    expect(liveAdapter.sendTypedTurn).toHaveBeenCalledWith(
      "Light provides energy.",
    );
    expect(candidateRequest).toMatchObject({
      origin: "student_verbatim",
      interaction: { kind: "direct_typed" },
    });
  });

  it("reuses a persisted candidate when review retry follows a server failure", async () => {
    let reviewAttempts = 0;
    const candidate = {
      candidate_id: "cand_runtime",
      candidate_version: 1,
      question_id: "q_runtime",
      text: "Exact retry text.",
      origin: "student_verbatim",
      attribution: "Your words",
      created_at: "2026-09-04T12:00:00Z",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/candidates")) {
        return new Response(JSON.stringify({ version: 4, candidate }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.endsWith("/review")) {
        reviewAttempts += 1;
        if (reviewAttempts === 1) {
          return new Response(
            JSON.stringify({
              error: {
                code: "review_unavailable",
                message: "Review is temporarily unavailable.",
                recoverable: true,
              },
              version: 4,
            }),
            {
              status: 503,
              headers: { "content-type": "application/json" },
            },
          );
        }
        return new Response(
          JSON.stringify({
            version: 4,
            question_id: "q_runtime",
            candidate,
            attribution: "Your words",
            review_token: "review_runtime",
            expires_at: "2026-09-04T12:10:00Z",
            placement: "appendix",
            preview_context_url:
              "/api/v2/assignments/asgn_runtime/pages/1/context?question_id=q_runtime",
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        );
      }
      return new Response(JSON.stringify(assignment), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    await user.type(
      screen.getByRole("textbox", { name: "Proposed answer" }),
      candidate.text,
    );
    await user.click(screen.getByRole("button", { name: "Review answer" }));
    expect(
      await screen.findByText("Review is temporarily unavailable."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review answer" }));
    expect(
      await screen.findByRole("heading", { name: "Review your exact answer" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          String(input).endsWith("/candidates"),
        ),
      ).toHaveLength(1);
    });
    expect(reviewAttempts).toBe(2);
  });

  it("does not let a delayed candidate response overwrite a newer local edit", async () => {
    const liveAdapter = {
      subscribe: vi.fn(() => vi.fn()),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(() => ({
        sessionId: "sess_deferred",
        sourceTurnIds: ["typed_deferred"],
        input: "typed" as const,
        normalization: "none" as const,
      })),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    let resolveCandidate!: (response: Response) => void;
    const candidateResponse = new Promise<Response>((resolve) => {
      resolveCandidate = resolve;
    });
    const reviewRequests: string[] = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL): Promise<Response> => {
        const url = String(input);
        if (url.endsWith("/candidates")) return candidateResponse;
        if (url.endsWith("/review")) reviewRequests.push(url);
        return new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    const editor = screen.getByRole("textbox", { name: "Proposed answer" });
    await user.type(editor, "Draft A");
    await user.click(screen.getByRole("button", { name: "Review answer" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/candidates"),
        ),
      ).toBe(true),
    );
    await user.clear(editor);
    await user.type(editor, "Draft B");

    act(() => {
      resolveCandidate(
        new Response(
          JSON.stringify({
            version: 4,
            candidate: {
              candidate_id: "cand_deferred_a",
              candidate_version: 1,
              question_id: "q_runtime",
              text: "Draft A",
              origin: "student_verbatim",
              attribution: "Your words",
              created_at: "2026-09-04T12:00:00Z",
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    });

    await waitFor(() => expect(editor).toHaveValue("Draft B"));
    expect(reviewRequests).toEqual([]);
    expect(
      screen.queryByRole("heading", { name: "Review your exact answer" }),
    ).not.toBeInTheDocument();
  });

  it("does not open exact review from a response for an older local draft", async () => {
    const liveAdapter = {
      subscribe: vi.fn(() => vi.fn()),
      connect: vi.fn(async () => ({ id: "connect", command: "connect" })),
      startListening: vi.fn(),
      stopListening: vi.fn(),
      interrupt: vi.fn(),
      setMuted: vi.fn(),
      sendTypedTurn: vi.fn(),
      registerTypedCandidate: vi.fn(() => ({
        sessionId: "sess_review_deferred",
        sourceTurnIds: ["typed_review_deferred"],
        input: "typed" as const,
        normalization: "none" as const,
      })),
      hearExact: vi.fn(),
      retry: vi.fn(),
      destroy: vi.fn(),
    };
    realtimeMocks.loadOpenAI.mockResolvedValue({
      createOpenAIRealtimeAdapter: () => liveAdapter,
    });
    const candidate = {
      candidate_id: "cand_review_a",
      candidate_version: 1,
      question_id: "q_runtime",
      text: "Draft A",
      origin: "student_verbatim",
      attribution: "Your words",
      created_at: "2026-09-04T12:00:00Z",
    };
    let resolveReview!: (response: Response) => void;
    const reviewResponse = new Promise<Response>((resolve) => {
      resolveReview = resolve;
    });
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL): Promise<Response> => {
        const url = String(input);
        if (url.endsWith("/candidates")) {
          return new Response(JSON.stringify({ version: 4, candidate }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        if (url.endsWith("/review")) return reviewResponse;
        return new Response(JSON.stringify(assignment), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/asgn_runtime"]}>
        <AppProviders>
          <RootApp />
        </AppProviders>
      </MemoryRouter>,
    );

    await screen.findByRole("heading", {
      name: "What is the runtime question?",
    });
    const editor = screen.getByRole("textbox", { name: "Proposed answer" });
    await user.type(editor, candidate.text);
    await user.click(screen.getByRole("button", { name: "Review answer" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/review"),
        ),
      ).toBe(true),
    );
    await user.clear(editor);
    await user.type(editor, "Draft B");

    act(() => {
      resolveReview(
        new Response(
          JSON.stringify({
            version: 4,
            question_id: "q_runtime",
            candidate,
            attribution: "Your words",
            review_token: "review_stale_a",
            expires_at: "2040-01-01T00:00:00Z",
            placement: "appendix",
            preview_context_url: "/context",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    });

    await waitFor(() => expect(editor).toHaveValue("Draft B"));
    expect(
      screen.queryByRole("heading", { name: "Review your exact answer" }),
    ).not.toBeInTheDocument();
  });
});
