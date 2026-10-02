import { useEffect, useRef, useState } from "react";
import { DEMO_DURATION_SECONDS, type DemoQuestionId } from "../../../lib/claros-demo-contract";

export type VoiceStatus = "idle" | "connecting" | "ready" | "listening" | "thinking" | "speaking" | "ended" | "error";
export type DemoMessage = { id: string; role: "user" | "assistant"; text: string };
const endpoint = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api/claros-demo`;
const activeStatuses: VoiceStatus[] = ["ready", "listening", "thinking", "speaking"];

export function useRealtimeDemo(questionId: DemoQuestionId) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<DemoMessage[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [micEnabled, setMicEnabled] = useState(false);
  const [hasMicrophone, setHasMicrophone] = useState(false);
  const [needsAudioPermission, setNeedsAudioPermission] = useState(false);
  const generation = useRef(0);
  const statusRef = useRef<VoiceStatus>("idle");
  const peer = useRef<RTCPeerConnection | null>(null);
  const channel = useRef<RTCDataChannel | null>(null);
  const microphone = useRef<MediaStream | null>(null);
  const speaker = useRef<HTMLAudioElement | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const frame = useRef<number | null>(null);
  const clock = useRef<ReturnType<typeof setInterval> | null>(null);
  const deadline = useRef<ReturnType<typeof setTimeout> | null>(null);
  const request = useRef<AbortController | null>(null);
  const lease = useRef<string | null>(null);
  const muted = useRef(false);

  function changeStatus(next: VoiceStatus) {
    statusRef.current = next;
    setStatus(next);
  }
  function releaseLease(leaseId: string) {
    void fetch(`${endpoint}/end`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ leaseId }), keepalive: true,
    }).catch(() => { /* The server independently enforces the demo deadline. */ });
  }
  function cleanup() {
    request.current?.abort();
    request.current = null;
    if (clock.current) clearInterval(clock.current);
    if (deadline.current) clearTimeout(deadline.current);
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    clock.current = null;
    deadline.current = null;
    frame.current = null;
    microphone.current?.getTracks().forEach(track => track.stop());
    microphone.current = null;
    channel.current?.close();
    channel.current = null;
    peer.current?.close();
    peer.current = null;
    speaker.current?.pause();
    if (speaker.current) speaker.current.srcObject = null;
    speaker.current = null;
    void audioContext.current?.close().catch(() => {});
    audioContext.current = null;
    if (lease.current) releaseLease(lease.current);
    lease.current = null;
  }
  function endSession() {
    generation.current++;
    cleanup();
    setAudioLevel(0);
    setMicEnabled(false);
    setHasMicrophone(false);
    setNeedsAudioPermission(false);
    changeStatus("ended");
  }
  useEffect(() => () => {
    generation.current++;
    cleanup();
  }, [questionId]);

  function fail(id: number, message: string) {
    if (generation.current !== id) return;
    generation.current++;
    cleanup();
    setAudioLevel(0);
    setMicEnabled(false);
    setHasMicrophone(false);
    setError(message);
    changeStatus("error");
  }
  function transcript(id: string, role: DemoMessage["role"], text: string, delta = false) {
    setMessages(previous => {
      const existing = previous.find(message => message.id === id);
      const next = { id, role, text: delta ? (existing?.text ?? "") + text : text };
      return existing
        ? previous.map(message => message.id === id ? next : message)
        : [...previous, next].slice(-20);
    });
  }
  async function resumeAudio() {
    try {
      await audioContext.current?.resume();
      await speaker.current?.play();
      setNeedsAudioPermission(false);
    } catch {
      setError("Your browser is still blocking audio. Allow sound for this page, then try Enable sound again.");
    }
  }
  async function start(mode: "voice" | "text") {
    const id = ++generation.current;
    cleanup();
    setError("");
    setMessages([]);
    setElapsed(0);
    setAudioLevel(0);
    setHasMicrophone(false);
    setMicEnabled(false);
    setNeedsAudioPermission(false);
    changeStatus("connecting");
    const controller = new AbortController();
    request.current = controller;
    deadline.current = setTimeout(() => fail(id, "The connection took too long. Please try again."), 35_000);
    try {
      // Unlock the audio context within the initiating user gesture.
      if (typeof AudioContext !== "undefined") {
        audioContext.current = new AudioContext();
        void audioContext.current.resume().catch(() => {});
      }
      const availability = await fetch(`${endpoint}/status`, { signal: controller.signal, cache: "no-store" });
      if (!availability.ok) throw new Error("The live demo server is unavailable. Please try again later.");
      const configuration = await availability.json();
      if (!configuration.ready) throw new Error("The live AI demo isn’t connected yet. The site owner needs to enable the OpenAI connection before you can start.");
      if (typeof RTCPeerConnection === "undefined") throw new Error("This browser doesn’t support live voice connections. Please use a current browser.");
      if (generation.current !== id) return;
      const connection = new RTCPeerConnection();
      peer.current = connection;
      const audio = new Audio();
      audio.autoplay = true;
      speaker.current = audio;
      connection.addEventListener("track", event => {
        if (generation.current !== id) return;
        const stream = event.streams[0] ?? new MediaStream([event.track]);
        audio.srcObject = stream;
        void audio.play().catch(() => {
          if (generation.current === id) setNeedsAudioPermission(true);
        });
        const context = audioContext.current;
        if (context) {
          const analyser = context.createAnalyser();
          analyser.fftSize = 256;
          context.createMediaStreamSource(stream).connect(analyser);
          const samples = new Uint8Array(analyser.fftSize);
          let lastUpdate = 0;
          const measure = (now: number) => {
            if (generation.current !== id) return;
            if (now - lastUpdate > 45) {
              analyser.getByteTimeDomainData(samples);
              let sum = 0;
              for (const sample of samples) sum += ((sample - 128) / 128) ** 2;
              setAudioLevel(Math.min(1, Math.sqrt(sum / samples.length) * 5));
              lastUpdate = now;
            }
            frame.current = requestAnimationFrame(measure);
          };
          frame.current = requestAnimationFrame(measure);
        }
      });
      connection.addEventListener("connectionstatechange", () => {
        if (connection.connectionState === "failed") fail(id, "The voice connection was interrupted. You can start a new conversation.");
      });
      if (mode === "voice") {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone access isn’t available here. Use typing instead, or open the full-size Preview in a supported browser.");
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (generation.current !== id) { stream.getTracks().forEach(track => track.stop()); return; }
        microphone.current = stream;
        muted.current = false;
        setHasMicrophone(true);
        setMicEnabled(true);
        stream.getAudioTracks().forEach(track => connection.addTrack(track, stream));
      } else {
        connection.addTransceiver("audio", { direction: "recvonly" });
      }
      const events = connection.createDataChannel("oai-events");
      channel.current = events;
      events.addEventListener("open", () => {
        if (generation.current !== id) return;
        if (deadline.current) clearTimeout(deadline.current);
        let seconds = 0;
        clock.current = setInterval(() => setElapsed(++seconds), 1000);
        deadline.current = setTimeout(endSession, DEMO_DURATION_SECONDS * 1000);
        changeStatus(mode === "voice" ? "listening" : "ready");
        // Per-response instructions replace the session prompt; keep the grounded server prompt intact.
        events.send(JSON.stringify({ type: "response.create" }));
      });
      events.addEventListener("close", () => fail(id, "This short conversation has ended. Start again whenever you’re ready."));
      events.addEventListener("message", ({ data }) => {
        if (generation.current !== id) return;
        let event: Record<string, unknown>;
        try { event = JSON.parse(data); } catch { return; }
        const itemId = String(event.item_id ?? event.response_id ?? "assistant");
        switch (event.type) {
          case "input_audio_buffer.speech_started":
            changeStatus("listening"); break;
          case "input_audio_buffer.speech_stopped":
          case "response.created":
            changeStatus("thinking"); break;
          case "output_audio_buffer.started":
            changeStatus("speaking"); break;
          case "output_audio_buffer.stopped":
          case "output_audio_buffer.cleared":
            changeStatus(mode === "voice" && !muted.current ? "listening" : "ready"); break;
          case "conversation.item.input_audio_transcription.completed":
            if (typeof event.transcript === "string") transcript(itemId, "user", event.transcript); break;
          case "conversation.item.input_audio_transcription.failed":
            setError("That speech couldn’t be transcribed. Try again, or type your message."); break;
          case "response.output_audio_transcript.delta":
          case "response.output_text.delta":
            if (typeof event.delta === "string") transcript(itemId, "assistant", event.delta, true); break;
          case "response.output_audio_transcript.done":
          case "response.output_text.done": {
            const text = event.transcript ?? event.text;
            if (typeof text === "string") transcript(itemId, "assistant", text);
            break;
          }
          case "response.done": {
            const response = event.response as { status?: string } | undefined;
            if (response?.status === "failed") fail(id, "The AI couldn’t complete that reply. Please start a new conversation.");
            else if (statusRef.current === "thinking") changeStatus(mode === "voice" && !muted.current ? "listening" : "ready");
            break;
          }
          case "error":
            fail(id, "The AI connection encountered an error. Please start again."); break;
        }
      });
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);
      if (connection.iceGatheringState !== "complete") {
        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(() => { remove(); resolve(); }, 3000);
          const onAbort = () => { remove(); reject(new DOMException("Cancelled", "AbortError")); };
          const onState = () => { if (connection.iceGatheringState === "complete") { remove(); resolve(); } };
          const remove = () => {
            clearTimeout(timer);
            controller.signal.removeEventListener("abort", onAbort);
            connection.removeEventListener("icegatheringstatechange", onState);
          };
          controller.signal.addEventListener("abort", onAbort, { once: true });
          connection.addEventListener("icegatheringstatechange", onState);
          onState();
        });
      }
      if (generation.current !== id) return;
      const result = await fetch(`${endpoint}/session`, {
        method: "POST", signal: controller.signal, headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sdp: connection.localDescription?.sdp, questionId, mode }),
      });
      if (!result.ok) {
        const body = await result.json().catch(() => ({}));
        throw new Error(body.message ?? "The AI session couldn’t start. Please try again later.");
      }
      const session = await result.json();
      if (generation.current !== id) { releaseLease(session.leaseId); return; }
      lease.current = session.leaseId;
      await connection.setRemoteDescription({ type: "answer", sdp: session.sdp });
    } catch (reason) {
      if (generation.current !== id) return;
      const denied = reason instanceof DOMException && ["NotAllowedError", "SecurityError"].includes(reason.name);
      const missingMic = reason instanceof DOMException && ["NotFoundError", "NotReadableError"].includes(reason.name);
      fail(id, denied
        ? "Microphone permission was blocked. Allow it in your browser, open the full-size Preview if needed, or use typing instead."
        : missingMic ? "No available microphone was found. Check your device, or use typing instead."
        : reason instanceof Error ? reason.message : "The live connection couldn’t start.");
    }
  }
  function sendMessage(text: string) {
    const value = text.trim();
    if (!value || value.length > 1000 || !channel.current || channel.current.readyState !== "open") return false;
    if (!["ready", "listening"].includes(statusRef.current)) return false;
    setError("");
    transcript(crypto.randomUUID(), "user", value);
    channel.current.send(JSON.stringify({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text: value }] } }));
    channel.current.send(JSON.stringify({ type: "response.create" }));
    changeStatus("thinking");
    return true;
  }
  function toggleMicrophone() {
    const tracks = microphone.current?.getAudioTracks();
    if (!tracks?.length) return;
    muted.current = !muted.current;
    tracks.forEach(track => { track.enabled = !muted.current; });
    setMicEnabled(!muted.current);
    if (["listening", "ready"].includes(statusRef.current)) changeStatus(muted.current ? "ready" : "listening");
  }
  return {
    status, error, messages, elapsed, audioLevel, micEnabled, hasMicrophone, needsAudioPermission,
    active: activeStatuses.includes(status), startVoice: () => start("voice"), startText: () => start("text"),
    endSession, sendMessage, toggleMicrophone, resumeAudio,
  };
}