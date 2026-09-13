import {
  CircleStop,
  Mic,
  MicOff,
  RefreshCw,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Button } from "@/v2/ui/Button";
import type { CaptureState, VoiceState } from "../../domain/contracts";

export type VoiceStateControlProps = {
  state: VoiceState;
  captureState?: CaptureState;
  muted?: boolean;
  onStart?: () => void;
  onStop?: () => void;
  onRetry?: () => void;
  onContinueByTyping?: () => void;
  onInterrupt?: () => void;
  onToggleMute?: () => void;
};

const voiceLabels: Record<VoiceState, string> = {
  ready: "Ready to listen",
  listening: "Listening",
  captured: "Words captured",
  thinking: "Claros is thinking",
  speaking: "Claros is speaking",
  interrupted: "Speech stopped",
  microphone_unavailable: "Microphone unavailable",
  disconnected: "Connection lost",
};

const helpForState: Record<VoiceState, string> = {
  ready: "Speak or type below.",
  listening: "Your words stay editable.",
  captured: "Review or keep talking.",
  thinking: "Your last response is safe.",
  speaking: "Interrupt at any time.",
  interrupted: "Your conversation is safe.",
  microphone_unavailable: "Retry voice or keep typing.",
  disconnected: "Retry voice or keep typing.",
};

export function VoiceStateControl({
  state,
  captureState = state === "listening" ? "active" : "inactive",
  muted = false,
  onStart,
  onStop,
  onRetry,
  onContinueByTyping,
  onInterrupt,
  onToggleMute,
}: VoiceStateControlProps) {
  const isFailure =
    state === "microphone_unavailable" || state === "disconnected";
  const isActive = state === "listening" || state === "speaking";

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--claros-line)] px-4 py-3"
      aria-label="Voice controls"
    >
      <div
        className="flex min-w-0 items-center gap-3"
        role="status"
        aria-live="polite"
      >
        <span
          className={`claros-voice-dot ${isActive ? "claros-voice-dot--active" : ""} ${isFailure ? "claros-voice-dot--error" : ""}`}
          aria-hidden="true"
        >
          <span />
          <span />
          <span />
        </span>
        <span className="min-w-0">
          <strong className="block truncate text-sm font-semibold text-[var(--claros-ink)]">
            {voiceLabels[state]}
          </strong>
          <small className="block truncate text-xs text-[var(--claros-muted)]">
            {helpForState[state]}
          </small>
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-1.5">
        {!isFailure && captureState !== "active" ? (
          <Button
            color="tertiary"
            size="sm"
            iconLeading={Mic}
            onPress={onStart}
            isDisabled={!onStart}
          >
            Start speaking
          </Button>
        ) : null}
        {!isFailure && captureState === "active" ? (
          <Button
            color="secondary"
            size="sm"
            iconLeading={CircleStop}
            onPress={onStop}
            isDisabled={!onStop}
          >
            Stop listening
          </Button>
        ) : null}
        {state === "speaking" ? (
          <Button
            color="secondary"
            size="sm"
            iconLeading={CircleStop}
            onPress={onInterrupt}
            isDisabled={!onInterrupt}
          >
            Interrupt Claros
          </Button>
        ) : null}
        {isFailure ? (
          <>
            <Button
              color="secondary"
              size="sm"
              iconLeading={RefreshCw}
              onPress={onRetry}
              isDisabled={!onRetry}
            >
              Retry voice
            </Button>
            <Button
              color="tertiary"
              size="sm"
              iconLeading={MicOff}
              onPress={onContinueByTyping}
              isDisabled={!onContinueByTyping}
            >
              Continue by typing
            </Button>
          </>
        ) : null}
        {onToggleMute && !isFailure ? (
          <Button
            color="tertiary"
            size="sm"
            iconLeading={muted ? VolumeX : Volume2}
            onPress={onToggleMute}
            aria-label={muted ? "Unmute spoken output" : "Mute spoken output"}
          >
            <span className="hidden xl:inline">
              {muted ? "Unmute" : "Mute"}
            </span>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
