import type {
  RealtimeAdapter,
  RealtimeCandidateEvidence,
  RealtimeConnectOptions,
  RealtimeEvent,
  RealtimeListener,
  RealtimeOperation,
} from "../../../src/v2/realtime/realtime-adapter";

const DEFAULT_REPLAY_ANSWER =
  "Plants need sunlight because light energy helps them make food.";
type UnidentifiedRealtimeEvent = RealtimeEvent extends infer Event
  ? Event extends { id: string }
    ? Omit<Event, "id">
    : never
  : never;

class BrowserReplayRealtimeAdapter implements RealtimeAdapter {
  private readonly listeners = new Set<RealtimeListener>();
  private readonly timers = new Set<number>();
  private options: RealtimeConnectOptions | null = null;
  private sequence = 0;
  private destroyed = false;
  private captureActive = false;

  subscribe(listener: RealtimeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  connect(options: RealtimeConnectOptions): RealtimeOperation {
    this.options = options;
    this.captureActive = Boolean(options.captureActive);
    this.emit({ type: "voice_state", state: "ready" });
    return this.operation("connect");
  }

  startListening(): RealtimeOperation {
    this.captureActive = true;
    if (this.scenario() === "microphone-unavailable") {
      this.emit({
        type: "error",
        code: "microphone_unavailable",
        message: "Microphone unavailable",
      });
    } else {
      this.emit({ type: "voice_state", state: "listening" });
      if (this.scenario() === "disconnect") {
        this.later(60, () => {
          this.captureActive = false;
          this.emit({
            type: "error",
            code: "realtime_disconnected",
            message: "Connection lost",
          });
        });
      }
    }
    return this.operation("listen");
  }

  stopListening(): RealtimeOperation {
    this.captureActive = false;
    this.clearTimers();
    if (this.scenario() !== "controls") {
      const text = this.answer();
      const turnId = this.nextId("student-caption");
      this.emit({
        type: "transcript",
        speaker: "student",
        text,
        final: true,
        sourceTurnId: turnId,
        sessionId: this.sessionId(),
        input: "voice",
      });
      this.emit({
        type: "candidate",
        text,
        input: "voice",
        normalization: "punctuation_only",
        sessionId: this.sessionId(),
        sourceTurnIds: [turnId],
      });
    }
    this.emit({ type: "voice_state", state: "captured" });
    return this.operation("stop");
  }

  interrupt(): RealtimeOperation {
    this.clearTimers();
    this.emit({ type: "voice_state", state: "interrupted" });
    return this.operation("interrupt");
  }

  setMuted(muted: boolean): RealtimeOperation {
    return this.operation("mute", muted);
  }

  sendTypedTurn(text: string): RealtimeOperation {
    this.emit({
      type: "transcript",
      speaker: "student",
      text,
      final: true,
      sourceTurnId: this.nextId("typed-turn"),
      sessionId: this.sessionId(),
      input: "typed",
    });

    const questionMatch = /(?:question|go to)\s+(\d+)/iu.exec(text);
    if (questionMatch) {
      this.emit({
        type: "navigate_question",
        destination: {
          kind: "index",
          questionIndex: Number(questionMatch[1]),
        },
      });
      return this.operation("typed_turn", text);
    }

    this.emit({ type: "voice_state", state: "thinking" });
    this.later(400, () => {
      this.emit({
        type: "transcript",
        speaker: "claros",
        text: "What detail from the question supports your answer?",
        final: true,
        sourceTurnId: this.nextId("claros-turn"),
        sessionId: this.sessionId(),
      });
      this.emit({ type: "voice_state", state: "speaking" });
      if (this.scenario() !== "controls") {
        this.later(800, () =>
          this.emit({ type: "voice_state", state: "ready" }),
        );
      }
    });
    return this.operation("typed_turn", text);
  }

  registerTypedCandidate(): RealtimeCandidateEvidence | null {
    return null;
  }

  hearExact(exactText: string): RealtimeOperation {
    const phrase = new URLSearchParams(window.location.search).get(
      "confirmation",
    );
    this.emit({ type: "voice_state", state: "speaking" });
    this.later(60, () => {
      this.emit({ type: "playback_complete", exactText });
      if (phrase) {
        this.emit({
          type: "transcript",
          speaker: "student",
          text: phrase,
          final: true,
          sourceTurnId: this.nextId("confirmation-caption"),
          sessionId: this.sessionId(),
          input: "voice",
        });
        this.emit({ type: "confirmation_phrase", phrase });
      }
      if (this.captureActive) {
        this.emit({ type: "voice_state", state: "listening" });
      } else {
        this.emit({ type: "voice_state", state: "ready" });
      }
    });
    return this.operation("hear_exact", exactText);
  }

  retry(): RealtimeOperation {
    this.emit({ type: "voice_state", state: "ready" });
    return this.operation("retry");
  }

  destroy(): RealtimeOperation {
    const operation = this.operation("destroy");
    this.destroyed = true;
    this.captureActive = false;
    this.clearTimers();
    this.listeners.clear();
    return operation;
  }

  private answer(): string {
    return (
      new URLSearchParams(window.location.search).get("answer") ??
      DEFAULT_REPLAY_ANSWER
    );
  }

  private scenario(): string {
    return (
      new URLSearchParams(window.location.search).get("replay") ?? "answer"
    );
  }

  private sessionId(): string {
    return `browser-replay-${this.options?.questionId ?? "unbound"}`;
  }

  private emit(event: UnidentifiedRealtimeEvent): void {
    if (this.destroyed) return;
    const identified = {
      ...event,
      id: this.nextId(event.type),
    } as RealtimeEvent;
    for (const listener of this.listeners) listener(identified);
  }

  private later(delay: number, callback: () => void): void {
    const timer = window.setTimeout(() => {
      this.timers.delete(timer);
      callback();
    }, delay);
    this.timers.add(timer);
  }

  private clearTimers(): void {
    for (const timer of this.timers) window.clearTimeout(timer);
    this.timers.clear();
  }

  private nextId(label: string): string {
    this.sequence += 1;
    return `browser-replay-${this.sequence}-${label}`;
  }

  private operation(
    command: RealtimeOperation["command"],
    payload?: string | boolean,
  ): RealtimeOperation {
    return {
      id: this.nextId(`operation-${command}`),
      command,
      ...(payload === undefined ? {} : { payload }),
    };
  }
}

export const createOpenAIRealtimeAdapter = (): RealtimeAdapter =>
  new BrowserReplayRealtimeAdapter();

export const loadOpenAIRealtimeAdapter = async () => ({
  createOpenAIRealtimeAdapter,
});
