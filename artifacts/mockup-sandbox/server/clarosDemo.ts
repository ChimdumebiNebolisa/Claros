import { createHash, randomBytes } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { DEMO_DURATION_SECONDS, DEMO_QUESTIONS } from "../src/lib/claros-demo-contract.ts";

type Options = {
  getApiKey?: () => string | undefined;
  fetchImpl?: typeof fetch;
  now?: () => number;
};
class RequestError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
type Lease = { callId: string; timer: ReturnType<typeof setTimeout> };

function json(response: ServerResponse, status: number, body: unknown) {
  if (response.destroyed || response.writableEnded) return;
  response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
  response.end(JSON.stringify(body));
}
async function readJson(request: IncomingMessage): Promise<Record<string, unknown>> {
  if (!request.headers["content-type"]?.toLowerCase().startsWith("application/json")) {
    throw new RequestError(415, "Send the request as JSON.");
  }
  if (Number(request.headers["content-length"]) > 65_536) {
    throw new RequestError(413, "The connection request is too large.");
  }
  let length = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    length += buffer.length;
    if (length > 65_536) throw new RequestError(413, "The connection request is too large.");
    chunks.push(buffer);
  }
  try {
    const value: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    return value as Record<string, unknown>;
  } catch {
    throw new RequestError(400, "The connection request is not valid JSON.");
  }
}
function allowedOrigin(request: IncomingMessage) {
  const origin = request.headers.origin;
  if (!origin) return false;
  try {
    const parsed = new URL(origin);
    const hosts = [request.headers.host, process.env.REPLIT_DEV_DOMAIN, ...(process.env.REPLIT_DOMAINS ?? "").split(",")];
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname);
    return hosts.includes(parsed.host) && (parsed.protocol === "https:" || (local && parsed.protocol === "http:"));
  } catch { return false; }
}

// This isolated preview never imports the original Claros assignment service.
export function createDemoMiddleware(basePath: string, options: Options = {}) {
  const prefix = `${basePath.replace(/\/$/, "")}/api/claros-demo`;
  const getApiKey = options.getApiKey ?? (() => process.env.OPENAI_API_KEY);
  const requestUpstream = options.fetchImpl ?? fetch;
  const now = options.now ?? Date.now;
  const leases = new Map<string, Lease>();
  const perVisitor = new Map<string, number[]>();
  let starts: number[] = [];
  let pending = 0;

  async function hangup(callId: string) {
    const key = getApiKey();
    if (!key) return;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const result = await requestUpstream(`https://api.openai.com/v1/realtime/calls/${encodeURIComponent(callId)}/hangup`, {
          method: "POST", headers: { Authorization: `Bearer ${key}` }, signal: AbortSignal.timeout(8000),
        });
        if (result.ok || result.status === 404) return;
      } catch { /* Retry once; never log credentials, SDP, or provider payloads. */ }
    }
    console.warn("The provider could not confirm that a preview voice session ended.");
  }
  async function endLease(id: string) {
    const current = leases.get(id);
    if (!current) return;
    clearTimeout(current.timer);
    leases.delete(id);
    await hangup(current.callId);
  }
  function reserveBudget(request: IncomingMessage) {
    const time = now();
    starts = starts.filter(start => time - start < 3_600_000);
    for (const [visitor, visits] of perVisitor) {
      const recent = visits.filter(start => time - start < 600_000);
      if (recent.length) perVisitor.set(visitor, recent);
      else perVisitor.delete(visitor);
    }
    if (starts.length >= 12 || leases.size + pending >= 3) {
      throw new RequestError(429, "This preview’s live demo limit has been reached. Please try again later.");
    }
    const visitor = createHash("sha256").update(`${request.socket.remoteAddress}|${request.headers["x-forwarded-for"] ?? ""}`).digest("hex");
    const recent = perVisitor.get(visitor) ?? [];
    if (recent.length >= 3) throw new RequestError(429, "You’ve reached this preview’s short demo limit. Please try again in ten minutes.");
    perVisitor.set(visitor, [...recent, time]);
    starts.push(time);
    return visitor;
  }
  async function handle(request: IncomingMessage, response: ServerResponse, next: () => void) {
    const path = request.url?.split("?")[0];
    if (!path?.startsWith(`${prefix}/`)) { next(); return; }
    let reserved = false;
    try {
      const route = path.slice(prefix.length);
      if (route === "/status" && request.method === "GET") {
        json(response, 200, { ready: Boolean(getApiKey()), durationSeconds: DEMO_DURATION_SECONDS });
        return;
      }
      if (request.method !== "POST") throw new RequestError(405, "This operation requires POST.");
      if (!allowedOrigin(request)) throw new RequestError(403, "Start the demo from this website.");
      const body = await readJson(request);
      if (route === "/end") {
        if (typeof body.leaseId !== "string" || !/^[\w-]{43}$/.test(body.leaseId)) throw new RequestError(400, "Invalid conversation reference.");
        await endLease(body.leaseId);
        if (!response.destroyed) { response.writeHead(204, { "Cache-Control": "no-store" }); response.end(); }
        return;
      }
      if (route !== "/session") throw new RequestError(404, "Demo operation not found.");
      if (typeof body.sdp !== "string" || !body.sdp.startsWith("v=0") || !body.sdp.includes("m=audio")) {
        throw new RequestError(400, "A valid audio connection offer is required.");
      }
      if (body.questionId !== "math" && body.questionId !== "english") throw new RequestError(400, "Choose one of the example questions.");
      if (body.mode !== "voice" && body.mode !== "text") throw new RequestError(400, "Choose voice or typing.");
      const key = getApiKey();
      if (!key) throw new RequestError(503, "The live AI demo isn’t connected yet. The site owner needs to enable the OpenAI connection.");
      const visitor = reserveBudget(request);
      pending++;
      reserved = true;
      const question = DEMO_QUESTIONS[body.questionId];
      const form = new FormData();
      form.set("sdp", body.sdp);
      form.set("session", JSON.stringify({
        type: "realtime",
        model: "gpt-realtime-2.1",
        output_modalities: ["audio"],
        max_output_tokens: 256,
        instructions: [
          "You are Claros AI, a supportive worksheet companion in a short public voice demo.",
          `The example question is: ${question.spokenQuestion}`,
          "Help the visitor work through this question with brief, clear, age-appropriate explanations and one small question at a time.",
          "Do not give the entire answer immediately. Respond naturally to their words; keep each reply under 60 words.",
          "Explain helpful next steps, not private internal chain-of-thought. Respect the student's ownership of their answer.",
          "Stay focused on this example question. Do not request personal details, offer unrelated advice, claim to upload or modify files, or call tools.",
          "This is a live AI demonstration, not a human tutor. Make that clear in your greeting.",
          "Begin with a greeting under 30 words: introduce yourself as Claros AI and ask one small first-step question about the specified example.",
          "The example is already visible on the page. Do not ask the visitor to supply or repeat the question.",
        ].join(" "),
        audio: {
          input: {
            transcription: { model: "gpt-4o-mini-transcribe" },
            turn_detection: { type: "server_vad", create_response: true, interrupt_response: true, silence_duration_ms: 650 },
          },
          output: { voice: "marin" },
        },
      }));
      const result = await requestUpstream("https://api.openai.com/v1/realtime/calls", {
        method: "POST", headers: { Authorization: `Bearer ${key}`, "OpenAI-Safety-Identifier": visitor },
        body: form, signal: AbortSignal.timeout(20_000),
      });
      if (!result.ok) {
        const message = result.status === 401 || result.status === 403
          ? "The AI provider rejected the connection. The site owner needs to check the API key and realtime model access."
          : result.status === 429
            ? "The AI provider’s usage limit has been reached. Please try again later."
            : "The AI provider couldn’t start this conversation. Please try again later.";
        throw new RequestError(502, message);
      }
      const location = result.headers.get("location");
      const locationUrl = location ? new URL(location, "https://api.openai.com") : null;
      const callId = locationUrl?.pathname.split("/").pop();
      if (!callId || locationUrl?.host !== "api.openai.com" || !/^[\w-]{1,200}$/.test(callId)) {
        throw new RequestError(502, "The AI provider returned an incomplete connection.");
      }
      const sdp = await result.text();
      if (!sdp.startsWith("v=0") || !sdp.includes("m=audio")) {
        await hangup(callId);
        throw new RequestError(502, "The AI provider returned an invalid connection.");
      }
      if (response.destroyed) { await hangup(callId); return; }
      const leaseId = randomBytes(32).toString("base64url");
      const timer = setTimeout(() => { void endLease(leaseId); }, DEMO_DURATION_SECONDS * 1000);
      timer.unref();
      leases.set(leaseId, { callId, timer });
      json(response, 201, { sdp, leaseId, durationSeconds: DEMO_DURATION_SECONDS });
    } catch (reason) {
      const status = reason instanceof RequestError ? reason.status : 502;
      json(response, status, { message: reason instanceof RequestError ? reason.message : "The live demo connection timed out or became unavailable. Please try again." });
    } finally {
      if (reserved) pending--;
    }
  }
  return {
    handle,
    close: async () => { await Promise.all([...leases.keys()].map(endLease)); },
  };
}

export function clarosDemoPlugin(basePath: string): Plugin {
  const service = createDemoMiddleware(basePath);
  return {
    name: "claros-live-voice-demo",
    configureServer(server) {
      server.middlewares.use((request, response, next) => { void service.handle(request, response, next); });
      server.httpServer?.once("close", () => { void service.close(); });
    },
    configurePreviewServer(server) {
      server.middlewares.use((request, response, next) => { void service.handle(request, response, next); });
      server.httpServer.once("close", () => { void service.close(); });
    },
  };
}