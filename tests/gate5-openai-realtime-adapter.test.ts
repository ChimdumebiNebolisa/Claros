import { describe, expect, it, vi } from "vitest";
import { RealtimeSession } from "@openai/agents/realtime";
import { createActor } from "xstate";
import {
  createClarosRealtimeAgent,
  OpenAIRealtimeAdapter,
  REALTIME_POLICY_VERSION,
  type RealtimeSessionLike,
  type SessionFactory,
  type SpeechPlayback,
} from "../src/v2/realtime/openai-realtime-adapter";
import realtimePolicy from "../backend/realtime/realtime-policy.json";
import type { RealtimeEvent } from "../src/v2/realtime/realtime-adapter";
import { fixtureAssignment } from "../src/v2/domain/fixtures";
import { workspaceMachine } from "../src/v2/domain/workspaceMachine";

type FactoryOptions = Parameters<SessionFactory>[0];
type EventName =
  | "transport_event"
  | "audio_start"
  | "audio_stopped"
  | "audio_interrupted"
  | "agent_end"
  | "error";

const credential = (sequence = 1) => ({
  version: 7,
  session_id: `sess_${sequence}`,
  client_secret: `ek_ephemeral_${sequence}`,
  expires_at: "2040-01-01T00:00:00Z",
  model: "gpt-realtime-2.1",
});

class FakeSession {
  readonly connect = vi.fn(async () => undefined);
  readonly sendMessage = vi.fn();
  readonly mute = vi.fn();
  readonly setOutputMuted = vi.fn();
  readonly interrupt = vi.fn();
  readonly close = vi.fn();
  readonly updateInstructions = vi.fn(async (instructions: string) => {
    void instructions;
  });
  private readonly listeners = new Map<
    EventName,
    Set<(...values: unknown[]) => void>
  >();
  readonly transport = {
    on: (
      event: "connection_change",
      listener: (status: "connecting" | "connected" | "disconnected") => void,
    ) => {
      this.connectionListener = listener;
    },
  };
  private connectionListener?: (
    status: "connecting" | "connected" | "disconnected",
  ) => void;

  on(event: EventName, listener: (...values: unknown[]) => void): void {
    const listeners = this.listeners.get(event) ?? new Set();
    listeners.add(listener);
    this.listeners.set(event, listeners);
  }

  emit(event: EventName, ...values: unknown[]): void {
    for (const listener of this.listeners.get(event) ?? []) listener(...values);
  }

  emitConnection(status: "connecting" | "connected" | "disconnected"): void {
    this.connectionListener?.(status);
  }
}

const setup = (overrides?: { playback?: SpeechPlayback }) => {
  const sessions: FakeSession[] = [];
  const factoryOptions: FactoryOptions[] = [];
  const factory: SessionFactory = (options) => {
    factoryOptions.push(options);
    const session = new FakeSession();
    sessions.push(session);
    return session as unknown as RealtimeSessionLike;
  };
  const credentialProvider = vi.fn(async () => credential(sessions.length + 1));
  const adapter = new OpenAIRealtimeAdapter(
    credentialProvider,
    factory,
    overrides?.playback,
  );
  const events: RealtimeEvent[] = [];
  adapter.subscribe((event) => events.push(event));
  return { adapter, credentialProvider, events, factoryOptions, sessions };
};

const connectOptions = {
  assignmentId: "asn_1",
  assignmentVersion: 7,
  questionId: "q_1",
  mode: "conversation" as const,
  exactQuestion: "How does sunlight help a plant make food?",
  relevantContext: ["Plants use light energy during photosynthesis."],
  currentCandidate: { id: "cand_1", version: 2, exactText: "My answer." },
};

describe("Gate 5 OpenAI Realtime adapter", () => {
  it("constructs the effective browser session tools from the authoritative policy", async () => {
    const callback = vi.fn(() => "test");
    const agent = createClarosRealtimeAgent("test instructions", {
      onCandidate: callback,
      onRephrase: callback,
      onExactReview: callback,
      onNavigateQuestion: callback,
    });

    expect(REALTIME_POLICY_VERSION).toBe(realtimePolicy.version);
    expect(
      agent.tools.map((registered) => ({
        name: registered.name,
        description:
          "description" in registered ? registered.description : undefined,
      })),
    ).toEqual(
      realtimePolicy.tools.map(({ name, description }) => ({
        name,
        description,
      })),
    );
    const sessionConfig = await RealtimeSession.computeInitialSessionConfig(
      agent,
      { model: "gpt-realtime-2.1", tracingDisabled: true },
    );
    const registeredTools = sessionConfig.tools as Array<{
      type: "function";
      name: string;
      description: string;
      parameters: Record<string, unknown>;
    }>;
    expect(
      registeredTools.map((registered) => {
        const parameters = { ...registered.parameters } as Record<
          string,
          unknown
        >;
        delete parameters.$schema;
        return {
          type: registered.type,
          name: registered.name,
          description: registered.description,
          parameters,
        };
      }),
    ).toEqual(realtimePolicy.tools);
  });

  it("fetches an owner-bound ephemeral credential and connects WebRTC with it", async () => {
    const { adapter, credentialProvider, events, factoryOptions, sessions } =
      setup();

    await adapter.connect(connectOptions);

    expect(credentialProvider).toHaveBeenCalledWith({
      assignment_id: "asn_1",
      assignment_version: 7,
      question_id: "q_1",
      mode: "conversation",
    });
    expect(sessions[0].connect).toHaveBeenCalledWith({
      apiKey: "ek_ephemeral_1",
      model: "gpt-realtime-2.1",
    });
    expect(factoryOptions[0].instructions).toContain(
      "UNTRUSTED_WORKSHEET_DATA=",
    );
    expect(factoryOptions[0].instructions).not.toContain("ek_ephemeral_1");
    expect(factoryOptions[0].microphone).toBe(true);
    expect(factoryOptions[0].reasoning).toBe("low");
    expect(events).toContainEqual(
      expect.objectContaining({ type: "voice_state", state: "ready" }),
    );
  });

  it("creates a text-only WebRTC session without requesting a microphone", async () => {
    const { adapter, factoryOptions } = setup();

    await adapter.connect({
      ...connectOptions,
      microphone: false,
    });

    expect(factoryOptions[0].microphone).toBe(false);
    expect(factoryOptions[0].reasoning).toBe("low");
    expect(factoryOptions[0].instructions).toContain(
      "One adaptive conversation:",
    );
    expect(factoryOptions[0].instructions).toContain(
      "Do not turn discussion, commands, hesitation, or ambiguous fragments into an answer",
    );
  });

  it("keeps the effective navigation tool and browser policy in agreement", async () => {
    const { adapter, factoryOptions } = setup();

    await adapter.connect({
      ...connectOptions,
      availableQuestions: [
        { id: "q_1", index: 1, prompt: "Question one" },
        { id: "q_2", index: 2, prompt: "Question two" },
      ],
    });

    expect(factoryOptions[0].instructions).toContain(
      "Navigate only to a question in the application-supplied question list",
    );
    expect(factoryOptions[0].instructions).not.toContain(
      "Never select another question",
    );
    expect(factoryOptions[0].instructions).toContain(
      "Do not provide a complete ready-to-submit answer",
    );
    expect(factoryOptions[0].instructions).toContain(
      "never output a complete sentence that directly answers the worksheet question",
    );
    expect(factoryOptions[0].instructions).toContain(
      "filled-in sentence frames, quoted templates",
    );
    expect(factoryOptions[0].instructions).toContain(
      "never offer a sentence starter, partial answer, fill-in-the-blank",
    );
    expect(factoryOptions[0].instructions).toContain(
      "Do not state the cause, result, role, or relationship",
    );
    expect(factoryOptions[0].instructions).toContain(
      "Ask the focused question without supplying the conclusion",
    );
    expect(factoryOptions[0].instructions).toContain(
      "make the tool call as your first output with no spoken or written preamble",
    );
  });

  it("does not spend the reconnect allowance on an initial credential failure", async () => {
    const credentialProvider = vi
      .fn()
      .mockRejectedValue(new Error("unavailable"));
    const factory = vi.fn() as unknown as SessionFactory;
    const adapter = new OpenAIRealtimeAdapter(credentialProvider, factory);
    const events: RealtimeEvent[] = [];
    adapter.subscribe((event) => events.push(event));

    await expect(adapter.connect(connectOptions)).rejects.toThrow(
      "unavailable",
    );

    expect(credentialProvider).toHaveBeenCalledOnce();
    expect(factory).not.toHaveBeenCalled();
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "error",
        code: "realtime_disconnected",
      }),
    );
  });

  it("maps captions and audio lifecycle while deduplicating provider event IDs", async () => {
    const { adapter, events, sessions } = setup();
    await adapter.connect(connectOptions);

    const studentTranscript = {
      type: "conversation.item.input_audio_transcription.completed",
      item_id: "turn_voice_1",
      transcript: "Sunlight gives the plant energy.",
    };
    sessions[0].emit("transport_event", {
      type: "input_audio_buffer.speech_started",
      event_id: "evt_speech_started",
    });
    sessions[0].emit("transport_event", {
      type: "response.created",
      event_id: "evt_response_created",
    });
    sessions[0].emit("transport_event", studentTranscript);
    sessions[0].emit("transport_event", studentTranscript);
    sessions[0].emit("transport_event", {
      type: "response.output_audio_transcript.delta",
      event_id: "evt_claros_delta",
      delta: "Good. ",
    });
    sessions[0].emit("transport_event", {
      type: "response.output_audio.delta",
      event_id: "evt_claros_audio_delta",
      delta: "not-retained-audio",
    });
    sessions[0].emit("transport_event", {
      type: "response.output_audio_transcript.done",
      event_id: "evt_claros_part_one",
      transcript: "Good.",
    });
    sessions[0].emit("transport_event", {
      type: "response.output_audio_transcript.delta",
      event_id: "evt_claros_delta_two",
      delta: "State your final answer.",
    });
    sessions[0].emit("transport_event", {
      type: "response.output_audio_transcript.done",
      event_id: "evt_claros_part_two",
      transcript: "State your final answer.",
    });
    sessions[0].emit("agent_end", {}, {}, "Good. State your final answer.");
    sessions[0].emit("audio_stopped");
    sessions[0].emit("audio_interrupted");

    expect(
      events.filter(
        (event) =>
          event.id ===
          "provider-conversation.item.input_audio_transcription.completed-turn_voice_1",
      ),
    ).toHaveLength(1);
    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "transcript",
          speaker: "student",
          final: true,
        }),
        expect.objectContaining({
          type: "transcript",
          speaker: "claros",
          final: false,
        }),
        expect.objectContaining({
          type: "transcript",
          speaker: "claros",
          text: "Good. State your final answer.",
          final: true,
        }),
        expect.objectContaining({ type: "voice_state", state: "listening" }),
        expect.objectContaining({ type: "voice_state", state: "thinking" }),
        expect.objectContaining({ type: "voice_state", state: "speaking" }),
        expect.objectContaining({ type: "voice_state", state: "interrupted" }),
      ]),
    );
  });

  it("binds candidate tools to matching application-owned student turns", async () => {
    const { adapter, events, factoryOptions, sessions } = setup();
    await adapter.connect(connectOptions);
    sessions[0].emit("transport_event", {
      type: "conversation.item.input_audio_transcription.completed",
      event_id: "evt_transcript",
      item_id: "turn_voice_1",
      transcript: "Plants use sunlight as energy.",
    });

    expect(
      await factoryOptions[0].onCandidate({
        exact_text: "No completed student turn says this.",
      }),
    ).toContain("Rejected");
    expect(
      await factoryOptions[0].onCandidate({
        exact_text: "Plants need water instead.",
      }),
    ).toContain("no matching completed student turn");
    const candidateResult = Promise.resolve(
      factoryOptions[0].onCandidate({
        exact_text: "Plants use sunlight as energy.",
      }),
    );
    const candidateAction = events.find((event) => event.type === "candidate");
    adapter.completeApplicationAction({
      actionId: candidateAction!.id,
      origin: candidateAction!.actionContext!,
      status: "accepted",
      message: "A local draft is ready.",
    });
    await expect(candidateResult).resolves.toContain("Accepted by application");
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "candidate",
        input: "voice",
        normalization: "none",
        sessionId: "sess_1",
        sourceTurnIds: ["turn_voice_1"],
      }),
    );
  });

  it("binds a draft after removing only an explicit student answer lead-in", async () => {
    const { adapter, events, factoryOptions } = setup();
    await adapter.connect(connectOptions);
    adapter.sendTypedTurn(
      "My answer is: Plants need sunlight because it provides energy.",
    );

    const candidateResult = Promise.resolve(
      factoryOptions[0].onCandidate({
        exact_text: "Plants need sunlight because it provides energy.",
      }),
    );
    const candidateAction = events.find((event) => event.type === "candidate");
    adapter.completeApplicationAction({
      actionId: candidateAction!.id,
      origin: candidateAction!.actionContext!,
      status: "accepted",
      message: "A local draft is ready.",
    });
    await expect(candidateResult).resolves.toContain("Accepted by application");

    expect(events).toContainEqual(
      expect.objectContaining({
        type: "candidate",
        text: "Plants need sunlight because it provides energy.",
        input: "typed",
      }),
    );
  });

  it("does not erase numeric or operator punctuation while matching a source turn", async () => {
    const unsafePairs = [
      ["-5", "5"],
      ["1.5", "15"],
      ["1/2", "12"],
      ["x+y", "xy"],
      ["1,000", "1000"],
    ] as const;

    for (const [spoken, changed] of unsafePairs) {
      const { adapter, factoryOptions } = setup();
      await adapter.connect({ ...connectOptions, currentCandidate: undefined });
      adapter.sendTypedTurn(spoken);
      expect(factoryOptions[0].onCandidate({ exact_text: changed })).toContain(
        "Rejected",
      );
    }
  });

  it("routes typed turns and binds current-draft intents without an opaque model ID", async () => {
    const { adapter, events, factoryOptions } = setup();
    await adapter.connect({ ...connectOptions, currentCandidate: undefined });

    adapter.sendTypedTurn("Plants use light energy.");
    const draftResult = Promise.resolve(
      factoryOptions[0].onCandidate({
        exact_text: "Plants use light energy.",
      }),
    );
    const draftAction = events.find((event) => event.type === "candidate");
    adapter.completeApplicationAction({
      actionId: draftAction!.id,
      origin: draftAction!.actionContext!,
      status: "accepted",
      message: "A local draft is ready.",
    });
    await draftResult;
    expect(adapter.registerTypedCandidate("My typed final answer.")).toEqual({
      sessionId: "sess_1",
      sourceTurnIds: [expect.any(String)],
      input: "typed",
      normalization: "none",
    });
    const rephraseResult = Promise.resolve(factoryOptions[0].onRephrase({}));
    const rephraseAction = events.find(
      (event) => event.type === "request_rephrase",
    );
    adapter.completeApplicationAction({
      actionId: rephraseAction!.id,
      origin: rephraseAction!.actionContext!,
      status: "accepted",
      message: "The wording comparison is ready.",
    });
    await rephraseResult;
    const reviewResult = Promise.resolve(factoryOptions[0].onExactReview({}));
    const reviewAction = events.find(
      (event) => event.type === "enter_exact_review",
    );
    adapter.completeApplicationAction({
      actionId: reviewAction!.id,
      origin: reviewAction!.actionContext!,
      status: "accepted",
      message: "Exact review is ready.",
    });
    await reviewResult;

    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "candidate", input: "typed" }),
        expect.objectContaining({ type: "request_rephrase" }),
        expect.objectContaining({ type: "enter_exact_review" }),
      ]),
    );
  });

  it("emits only application-grounded question navigation", async () => {
    const { adapter, events, factoryOptions } = setup();
    await adapter.connect({
      ...connectOptions,
      availableQuestions: [
        { id: "q_1", index: 1, prompt: "Question one" },
        { id: "q_2", index: 2, prompt: "Question two" },
      ],
    });

    expect(factoryOptions[0].onNavigateQuestion({ destination: 3 })).toContain(
      "Rejected",
    );
    const navigationResult = Promise.resolve(
      factoryOptions[0].onNavigateQuestion({ destination: 2 }),
    );
    const navigationAction = events.find(
      (event) => event.type === "navigate_question",
    );
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "navigate_question",
        destination: { kind: "index", questionIndex: 2 },
      }),
    );
    expect(
      events.filter((event) => event.type === "navigate_question"),
    ).toHaveLength(1);
    adapter.completeApplicationAction({
      actionId: navigationAction!.id,
      origin: navigationAction!.actionContext!,
      status: "accepted",
      message: "Now on Question 2: Question two",
    });
    await expect(navigationResult).resolves.toContain(
      "Accepted by application",
    );
  });

  it("waits for the application outcome before reporting navigation success", async () => {
    const { adapter, events, factoryOptions } = setup();
    await adapter.connect({
      ...connectOptions,
      currentCandidate: undefined,
      availableQuestions: [
        { id: "q_1", index: 1, prompt: "Question one" },
        { id: "q_2", index: 2, prompt: "Question two" },
      ],
    });

    let settled = false;
    const result = Promise.resolve(
      factoryOptions[0].onNavigateQuestion({ destination: 2 }),
    ).then((value) => {
      settled = true;
      return value;
    });
    await Promise.resolve();

    expect(settled).toBe(false);
    const action = events.find((event) => event.type === "navigate_question");
    expect(action).toBeDefined();
    (
      adapter as unknown as {
        completeApplicationAction(outcome: {
          actionId: string;
          origin: NonNullable<
            Extract<
              RealtimeEvent,
              { type: "navigate_question" }
            >["actionContext"]
          >;
          status: "accepted";
          message: string;
        }): void;
      }
    ).completeApplicationAction({
      actionId: action!.id,
      origin: action!.actionContext!,
      status: "accepted",
      message: "Now on Question 2: Question two",
    });

    await expect(result).resolves.toBe(
      "Accepted by application: Now on Question 2: Question two",
    );
  });

  it("returns stale and replaced action results as superseded, never successful", async () => {
    const { adapter, events, factoryOptions } = setup();
    await adapter.connect({
      ...connectOptions,
      currentCandidate: undefined,
      availableQuestions: [
        { id: "q_1", index: 1, prompt: "Question one" },
        { id: "q_2", index: 2, prompt: "Question two" },
      ],
    });

    const older = Promise.resolve(
      factoryOptions[0].onNavigateQuestion({ destination: "next" }),
    );
    const newer = Promise.resolve(
      factoryOptions[0].onNavigateQuestion({ destination: 2 }),
    );
    await expect(older).resolves.toContain("Superseded by application");

    const latest = events
      .filter((event) => event.type === "navigate_question")
      .at(-1)!;
    adapter.completeApplicationAction({
      actionId: latest.id,
      origin: {
        ...latest.actionContext!,
        contextEpoch: latest.actionContext!.contextEpoch + 1,
      },
      status: "accepted",
      message: "Now on Question 2: Question two",
    });
    await expect(newer).resolves.toContain("Superseded by application");
  });

  it("updates the live agent with distinct application-owned workflow states", async () => {
    const { adapter, sessions } = setup();
    await adapter.connect({ ...connectOptions, currentCandidate: undefined });
    const base = {
      assignmentId: "asn_1",
      assignmentVersion: 7,
      questionId: "q_1",
      contextEpoch: 3,
      activeQuestionIndex: 1,
      activeQuestionText: "How does sunlight help a plant make food?",
      approvedExactText: undefined,
      failureCode: undefined,
    } as const;

    await adapter.updateApplicationState({
      ...base,
      draft: { status: "local", exactText: "My local words." },
      reviewStatus: "not_ready",
      approvalStatus: "not_approved",
      exportStatus: "not_started",
    });
    await adapter.updateApplicationState({
      ...base,
      assignmentVersion: 8,
      draft: {
        status: "persisted",
        exactText: "My local words.",
        candidateId: "cand_1",
        candidateVersion: 1,
      },
      reviewStatus: "ready",
      approvalStatus: "not_approved",
      exportStatus: "not_started",
    });
    await adapter.updateApplicationState({
      ...base,
      assignmentVersion: 9,
      draft: {
        status: "persisted",
        exactText: "My local words.",
        candidateId: "cand_1",
        candidateVersion: 1,
      },
      reviewStatus: "not_ready",
      approvalStatus: "approved",
      approvedExactText: "My local words.",
      exportStatus: "complete",
    });

    const updates = sessions[0].updateInstructions.mock.calls.map(
      ([instructions]) => String(instructions),
    );
    expect(
      updates.some((value) => value.includes('"draft_status":"local"')),
    ).toBe(true);
    expect(
      updates.some(
        (value) =>
          value.includes('"draft_status":"persisted"') &&
          value.includes('"review_status":"ready"') &&
          value.includes('"approval_status":"not_approved"'),
      ),
    ).toBe(true);
    expect(updates.at(-1)).toContain('"approval_status":"approved"');
    expect(updates.at(-1)).toContain('"export_status":"complete"');
  });

  it("supports mute, stop, interrupt, exact playback, and teardown", async () => {
    const complete = vi.fn();
    const playback: SpeechPlayback = {
      speak: vi.fn((_text, onComplete) => {
        complete.mockImplementation(onComplete);
      }),
      cancel: vi.fn(),
    };
    const { adapter, events, sessions } = setup({ playback });
    await adapter.connect(connectOptions);

    adapter.startListening();
    adapter.stopListening();
    adapter.setMuted(true);
    adapter.interrupt();
    adapter.hearExact("My exact answer.");
    complete();
    adapter.destroy();

    expect(sessions[0].mute.mock.calls).toEqual([[true], [false], [true]]);
    expect(sessions[0].setOutputMuted).toHaveBeenCalledWith(true);
    expect(sessions[0].interrupt).toHaveBeenCalledOnce();
    expect(sessions[0].close).toHaveBeenCalledOnce();
    expect(playback.cancel).toHaveBeenCalledOnce();
    expect(events).toContainEqual(
      expect.objectContaining({
        id: expect.stringContaining("ready-after-stop"),
        type: "voice_state",
        state: "ready",
      }),
    );
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "playback_complete",
        exactText: "My exact answer.",
      }),
    );
  });

  it("uses one automatic reconnect and then surfaces a recoverable disconnect", async () => {
    const { adapter, credentialProvider, events, sessions } = setup();
    await adapter.connect(connectOptions);

    sessions[0].emitConnection("disconnected");
    await vi.waitFor(() => expect(sessions).toHaveLength(2));
    sessions[1].emitConnection("disconnected");

    expect(credentialProvider).toHaveBeenCalledTimes(2);
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "error",
        code: "realtime_disconnected",
      }),
    );
  });

  it("preserves a manual input pause through automatic reconnect", async () => {
    const { adapter, sessions } = setup();
    await adapter.connect(connectOptions);
    adapter.startListening();
    adapter.stopListening();

    sessions[0].emitConnection("disconnected");
    await vi.waitFor(() => expect(sessions).toHaveLength(2));

    expect(sessions[1].mute).toHaveBeenLastCalledWith(true);
  });

  it("preserves recent conversation in the automatic reconnect prompt", async () => {
    const { adapter, factoryOptions, sessions } = setup();
    await adapter.connect({
      ...connectOptions,
      conversationHistory: [
        {
          speaker: "student",
          text: "Can you help me think about sunlight?",
          questionId: "q_1",
        },
        {
          speaker: "claros",
          text: "What does sunlight provide?",
          questionId: "q_1",
        },
      ],
    });

    sessions[0].emit("transport_event", {
      type: "conversation.item.input_audio_transcription.completed",
      event_id: "evt_answer",
      item_id: "turn_voice_answer",
      transcript: "It gives the plant energy.",
    });
    sessions[0].emitConnection("disconnected");
    await vi.waitFor(() => expect(factoryOptions).toHaveLength(2));

    expect(factoryOptions[1].instructions).toContain(
      "Can you help me think about sunlight?",
    );
    expect(factoryOptions[1].instructions).toContain(
      "It gives the plant energy.",
    );
  });

  it("drives the real adapter transcript and draft through the conversation machine after ready", async () => {
    const { adapter, events, factoryOptions, sessions } = setup();
    const actor = createActor(workspaceMachine).start();
    actor.send({ type: "START_ANALYSIS" });
    actor.send({ type: "ANALYSIS_READY", assignment: fixtureAssignment });
    actor.send({ type: "START_QUESTION" });
    adapter.subscribe((event) => {
      if (event.type === "voice_state") {
        actor.send({ type: "VOICE_STATE_CHANGED", state: event.state });
      } else if (
        event.type === "transcript" &&
        event.final &&
        event.speaker === "student"
      ) {
        actor.send({
          type: "GUIDED_STUDENT_TURN",
          text: event.text,
          sourceTurnId: event.sourceTurnId,
          sessionId: event.sessionId,
          input: event.input,
        });
      } else if (event.type === "candidate") {
        actor.send({ type: "VOICE_CAPTURED", text: event.text });
      }
    });

    await adapter.connect({ ...connectOptions, currentCandidate: undefined });
    expect(actor.getSnapshot().matches("conversation")).toBe(true);
    expect(actor.getSnapshot().context.voiceState).toBe("ready");

    sessions[0].emit("transport_event", {
      type: "conversation.item.input_audio_transcription.completed",
      event_id: "evt_final_answer",
      item_id: "turn_voice_final",
      transcript: "Plants use sunlight as energy.",
    });
    const candidateResult = Promise.resolve(
      factoryOptions[0].onCandidate({
        exact_text: "Plants use sunlight as energy.",
      }),
    );
    const candidateAction = events.find((event) => event.type === "candidate");
    adapter.completeApplicationAction({
      actionId: candidateAction!.id,
      origin: candidateAction!.actionContext!,
      status: "accepted",
      message: "A local draft is ready.",
    });
    await candidateResult;

    const snapshot = actor.getSnapshot();
    expect(snapshot.matches("conversation")).toBe(true);
    expect(snapshot.context.candidate?.text).toBe(
      "Plants use sunlight as energy.",
    );
    expect(snapshot.context.guidedTurns.at(-1)).toEqual(
      expect.objectContaining({
        speaker: "student",
        sourceTurnId: "turn_voice_final",
        sessionId: "sess_1",
        input: "voice",
      }),
    );
  });

  it("does not finalize a partial assistant transcript after interruption", async () => {
    const { adapter, events, sessions } = setup();
    await adapter.connect(connectOptions);

    sessions[0].emit("transport_event", {
      type: "response.created",
      event_id: "evt_response_created",
    });
    sessions[0].emit("transport_event", {
      type: "response.output_audio_transcript.done",
      event_id: "evt_partial_done",
      transcript: "This reply was interrupted",
    });
    adapter.interrupt();
    sessions[0].emit("agent_end", {}, {}, "This reply was interrupted");

    expect(
      events.filter(
        (event) => event.type === "transcript" && event.speaker === "claros",
      ),
    ).toEqual([]);
  });

  it("surfaces a disconnect when the single automatic reconnect fails", async () => {
    const { adapter, credentialProvider, events, sessions } = setup();
    await adapter.connect(connectOptions);
    adapter.startListening();
    credentialProvider.mockRejectedValueOnce(new Error("provider unavailable"));

    sessions[0].emitConnection("disconnected");
    await vi.waitFor(() =>
      expect(events).toContainEqual(
        expect.objectContaining({
          type: "error",
          code: "realtime_disconnected",
        }),
      ),
    );

    expect(credentialProvider).toHaveBeenCalledTimes(2);
    expect(sessions[0].close).toHaveBeenCalled();

    await adapter.retry();
    expect(sessions[1].mute).toHaveBeenLastCalledWith(true);
  });

  it("does not reconnect after microphone permission denial", async () => {
    const { adapter, credentialProvider, events, sessions } = setup();
    await adapter.connect(connectOptions);

    sessions[0].emit("error", new DOMException("Denied", "NotAllowedError"));

    expect(credentialProvider).toHaveBeenCalledOnce();
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "error",
        code: "microphone_unavailable",
      }),
    );
  });
});
