import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { buildWorksheetPdf, createDemoWorksheet, demoPdf, demoSourceHash } from "./fixture.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const assignments = new Map();
const plans = new Map();
const sessions = new Map();
const MAX_REQUEST_BYTES = 10 * 1024 * 1024;
const planInputSchema = z.object({ questionId: z.string().min(1).max(100), answerText: z.string().max(2000) });
const commitInputSchema = z.object({ planToken: z.string().min(20).max(200) });

function json(response, status, payload, headers = {}) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", ...headers });
  response.end(JSON.stringify(payload));
}

function cookieValue(request, name) {
  const cookies = request.headers.cookie?.split(";").map((part) => part.trim()) ?? [];
  const value = cookies.find((part) => part.startsWith(`${name}=`));
  return value?.slice(name.length + 1) ?? null;
}

function sessionFor(request, response) {
  let sessionId = cookieValue(request, "claros_sid");
  if (!sessionId || !sessions.has(sessionId)) {
    sessionId = randomBytes(24).toString("base64url");
    sessions.set(sessionId, new Set());
    response.setHeader("set-cookie", `claros_sid=${sessionId}; HttpOnly; SameSite=Lax; Path=/`);
  }
  return { sessionId, assignmentIds: sessions.get(sessionId) };
}

async function bodyBuffer(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.from(chunk);
    size += buffer.length;
    if (size > MAX_REQUEST_BYTES) {
      const error = new Error("request too large");
      error.statusCode = 413;
      throw error;
    }
    chunks.push(buffer);
  }
  return Buffer.concat(chunks);
}

async function bodyJson(request) {
  const body = await bodyBuffer(request);
  try { return JSON.parse(body.toString("utf8")); } catch { return {}; }
}

function extractPdf(body) {
  const start = body.indexOf(Buffer.from("%PDF-"));
  const endMarker = Buffer.from("%%EOF");
  const endIndex = body.lastIndexOf(endMarker);
  if (start < 0 || endIndex < start) return null;
  let end = endIndex + endMarker.length;
  if (body[end] === 13 && body[end + 1] === 10) end += 2;
  else if (body[end] === 10) end += 1;
  return body.subarray(start, end);
}

function newAssignment(session, response) {
  const id = `assignment_${randomBytes(8).toString("hex")}`;
  const worksheet = createDemoWorksheet();
  const assignment = { id, worksheet, committedAnswers: [], activeQuestionId: worksheet.questions[0].id };
  assignments.set(id, assignment);
  session.assignmentIds.add(id);
  return assignment;
}

function ownedAssignment(request, response, id) {
  const sessionId = cookieValue(request, "claros_sid");
  const owned = sessionId && sessions.get(sessionId)?.has(id);
  const assignment = assignments.get(id);
  if (!owned || !assignment) {
    json(response, 404, { error: { code: "assignment_not_found", message: "This worksheet session is no longer available." } });
    return null;
  }
  return assignment;
}

function planFor(assignment, questionId, answerText) {
  const question = assignment.worksheet.questions.find((item) => item.id === questionId);
  if (!question || typeof answerText !== "string") return null;
  const lineCount = answerText.split(/\r?\n/).reduce((total, line) => total + Math.max(1, Math.ceil(line.length / 58)), 0);
  const availableLines = Math.max(1, Math.floor(question.answerRegion.bounds.height / 18));
  const placement = lineCount <= availableLines ? "fits_in_answer_area" : lineCount <= availableLines + 5 ? "requires_continuation_page" : "blocked";
  const planToken = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + 5 * 60_000).toISOString();
  const plan = { questionId, answerText, placement, planToken, expiresAt };
  plans.set(planToken, { assignmentId: assignment.id, plan });
  return plan;
}

function safeEqual(a, b) {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

async function handleApi(request, response, pathname) {
  if (request.method === "GET" && pathname === "/health") {
    json(response, 200, { status: "ok" });
    return true;
  }
  if (request.method === "GET" && pathname === "/api/v1/demo.pdf") {
    response.writeHead(200, { "content-type": "application/pdf", "content-disposition": 'attachment; filename="ecosystems-worksheet.pdf"' });
    response.end(demoPdf);
    return true;
  }
  if (request.method === "GET" && pathname === "/api/v1/demo") {
    const session = sessionFor(request, response);
    const assignment = newAssignment(session, response);
    json(response, 200, { assignment });
    return true;
  }
  const assignmentMatch = pathname.match(/^\/api\/v1\/assignments\/([^/]+)(?:\/(plan|commit|export))?$/);
  if (request.method === "POST" && pathname === "/api/v1/assignments") {
    const session = sessionFor(request, response);
    const body = await bodyBuffer(request);
    const pdf = extractPdf(body);
    if (!pdf) {
      json(response, 422, { error: { code: "document_parse_failed", message: "Claros could not read this upload as a PDF with selectable text." } });
      return true;
    }
    const hash = createHash("sha256").update(pdf).digest("hex");
    if (hash !== demoSourceHash) {
      json(response, 422, { error: { code: "document_validation_failed", message: "This worksheet is outside Claros' supported short-answer contract. Download the sample worksheet to try the complete flow." } });
      return true;
    }
    const assignment = newAssignment(session, response);
    json(response, 201, { assignment });
    return true;
  }
  if (!assignmentMatch) return false;
  const [, assignmentId, action] = assignmentMatch;
  const assignment = ownedAssignment(request, response, assignmentId);
  if (!assignment) return true;
  if (request.method === "GET" && !action) { json(response, 200, { assignment }); return true; }
  if (request.method === "POST" && action === "plan") {
    const input = await bodyJson(request);
    const parsed = planInputSchema.safeParse(input);
    const plan = parsed.success ? planFor(assignment, parsed.data.questionId, parsed.data.answerText) : null;
    if (!plan) { json(response, 422, { error: { code: "document_validation_failed", message: "That answer could not be associated with the active question." } }); return true; }
    json(response, 200, { plan });
    return true;
  }
  if (request.method === "POST" && action === "commit") {
    const input = await bodyJson(request);
    const parsed = commitInputSchema.safeParse(input);
    const stored = parsed.success ? plans.get(parsed.data.planToken) : null;
    if (!stored || stored.assignmentId !== assignment.id || new Date(stored.plan.expiresAt) < new Date()) {
      json(response, 409, { error: { code: "stale_plan", message: "This review is out of date. Review the exact answer again before adding it." } });
      return true;
    }
    if (!safeEqual(stored.plan.planToken, parsed.data.planToken) || stored.plan.placement === "blocked") {
      json(response, 409, { error: { code: "placement_blocked", message: "Placement needs attention before this answer can be added." } });
      return true;
    }
    const existing = assignment.committedAnswers.find((item) => item.questionId === stored.plan.questionId);
    const committed = { questionId: stored.plan.questionId, text: stored.plan.answerText, placement: stored.plan.placement, revision: (existing?.revision ?? 0) + 1, committedAt: new Date().toISOString() };
    assignment.committedAnswers = [...assignment.committedAnswers.filter((item) => item.questionId !== committed.questionId), committed];
    assignment.activeQuestionId = assignment.worksheet.questions.find((item) => item.index === (assignment.worksheet.questions.find((q) => q.id === committed.questionId)?.index ?? 0) + 1)?.id ?? committed.questionId;
    json(response, 200, { assignment });
    return true;
  }
  if (request.method === "GET" && action === "export") {
    if (assignment.committedAnswers.length !== assignment.worksheet.questions.length) {
      json(response, 409, { error: { code: "incomplete_assignment", message: "Finish each question before exporting the completed worksheet." } });
      return true;
    }
    if (assignment.committedAnswers.some((item) => /[^\x20-\x7E\n\r\t]/.test(item.text))) {
      json(response, 422, { error: { code: "unicode_rendering_failed", message: "This answer contains characters the current PDF renderer cannot safely reproduce. Edit the answer and review it again." } });
      return true;
    }
    const answers = assignment.worksheet.questions.map((question) => assignment.committedAnswers.find((answer) => answer.questionId === question.id)?.text ?? "");
    const pdf = buildWorksheetPdf(answers);
    response.writeHead(200, { "content-type": "application/pdf", "content-disposition": 'attachment; filename="claros-completed-worksheet.pdf"' });
    response.end(pdf);
    return true;
  }
  return false;
}

async function serveStatic(request, response, pathname) {
  const requested = pathname === "/" ? "/index.html" : pathname;
  const filePath = join(root, "dist", requested.replace(/^\//, ""));
  try {
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) throw new Error("not a file");
    const body = await readFile(filePath);
    const ext = extname(filePath);
    const contentType = ext === ".html" ? "text/html; charset=utf-8" : ext === ".js" ? "text/javascript" : ext === ".css" ? "text/css" : "application/octet-stream";
    response.writeHead(200, { "content-type": contentType });
    response.end(body);
  } catch {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", "http://localhost");
  for (const [name, value] of Object.entries({
    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(self), geolocation=()",
  })) response.setHeader(name, value);
  try {
    if (!(await handleApi(request, response, url.pathname))) await serveStatic(request, response, url.pathname);
  } catch (error) {
    console.error("request failed", error instanceof Error ? error.message : "unknown error");
    if (!response.headersSent) {
      const status = error?.statusCode === 413 ? 413 : 500;
      const code = status === 413 ? "upload_too_large" : "internal_error";
      const message = status === 413 ? "This upload is larger than Claros supports." : "Claros could not complete that action.";
      json(response, status, { error: { code, message } });
    }
  }
});

const port = Number(process.env.PORT ?? 8787);
server.listen(port, () => console.log(`Claros API listening on http://localhost:${port}`));
