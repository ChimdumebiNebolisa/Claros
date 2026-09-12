import { describe, expect, it, vi } from "vitest";
import {
  OpenAIRealtimeAdapter,
  type RealtimeSessionLike,
  type SessionFactory,
  type SpeechPlayback,
} from "../src/v2/realtime/openai-realtime-adapter";
import type { RealtimeEvent } from "../src/v2/realtime/realtime-adapter";

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
  readonly interrupt = vi.fn();
  readonly close = vi.fn();
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
  mode: "guided" as const,
  exactQuestion: "How does sunlight help a plant make food?",
  relevantContext: ["Plants use light energy during photosynthesis."],
  currentCandidate: { id: "cand_1", version: 2, exactText: "My answer." },
};

describe("Gate 5 OpenAI Realtime adapter", () => {
  it("fetches an owner-bound ephemeral credential and connects WebRTC with it", async () => {
    const { adapter, credentialProvider, events, factoryOptions, sessions } =
      setup();

    await adapter.connect(connectOptions);

    expect(credentialProvider).toHaveBeenCalledWith({
      assignment_id: "asn_1",
      assignment_version: 7,
      question_id: "q_1",
      mode: "guided",
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
      mode: "direct",
      microphone: false,
    });

    expect(factoryOptions[0].microphone).toBe(false);
    expect(factoryOptions[0].reasoning).toBe("minimal");
    expect(factoryOptions[0].instructions).toContain("Direct-answer mode:");
    expect(factoryOptions[0].instructions).toContain(
      "Do not turn a fragment into a materially more complete answer without permission.",
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

  it("accepts candidate tools only when every source turn is trusted", async () => {
    const { adapter, events, factoryOptions, sessions } = setup();
    await adapter.connect(connectOptions);
    sessions[0].emit("transport_event", {
      type: "conversation.item.input_audio_transcription.completed",
      event_id: "evt_transcript",
      item_id: "turn_voice_1",
      transcript: "Plants use sunlight as energy.",
    });

    expect(
      factoryOptions[0].onCandidate({
        exact_text: "Plants use sunlight as energy.",
        source_turn_ids: ["missing_turn"],
      }),
    ).toContain("Rejected");
    expect(
      factoryOptions[0].onCandidate({
        exact_text: "Plants need water instead.",
        source_turn_ids: ["turn_voice_1"],
      }),
    ).toContain("changed the student's words");
    expect(
      factoryOptions[0].onCandidate({
        exact_text: "Plants use sunlight as energy.",
        source_turn_ids: ["turn_voice_1"],
      }),
    ).toContain("sent");
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

  it("routes typed turns and candidate-scoped application intents", async () => {
    const { adapter, events, factoryOptions, sessions } = setup();
    await adapter.connect(connectOptions);

    adapter.sendTypedTurn("Plants use light energy.");
    const typedEventId = sessions[0].sendMessage.mock.calls[0][1]
      .event_id as string;
    factoryOptions[0].onCandidate({
      exact_text: "Plants use light energy.",
      source_turn_ids: [typedEventId],
    });
    expect(adapter.registerTypedCandidate("My typed final answer.")).toEqual({
      sessionId: "sess_1",
      sourceTurnIds: [expect.any(String)],
      input: "typed",
      normalization: "none",
    });
    expect(factoryOptions[0].onRephrase({ candidate_id: "stale" })).toContain(
      "Rejected",
    );
    factoryOptions[0].onRephrase({ candidate_id: "cand_1" });
    factoryOptions[0].onExactReview({ candidate_id: "cand_1" });

    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "candidate", input: "typed" }),
        expect.objectContaining({
          type: "request_rephrase",
          candidateId: "cand_1",
        }),
        expect.objectContaining({
          type: "enter_exact_review",
          candidateId: "cand_1",
        }),
      ]),
    );
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

    expect(sessions[0].mute.mock.calls).toEqual([[false], [true], [true]]);
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
