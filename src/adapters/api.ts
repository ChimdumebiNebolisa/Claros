import { assignmentSchema, placementPlanSchema, type Assignment, type PlacementPlan, type RejectionCode } from "../domain/contracts";

type ApiErrorShape = { error?: { code?: RejectionCode; message?: string } };

async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, { credentials: "include", ...init });
  const body = (await response.json().catch(() => ({}))) as T & ApiErrorShape;
  if (!response.ok) {
    const apiError = body.error;
    throw new Error(apiError?.message ?? "Claros could not complete that action.");
  }
  return body as T;
}

export async function loadDemoAssignment(): Promise<Assignment> {
  const result = await request<{ assignment: Assignment }>("/api/v1/demo");
  return assignmentSchema.parse(result.assignment);
}

export async function uploadWorksheet(file: File): Promise<Assignment> {
  const formData = new FormData();
  formData.append("file", file);
  const result = await request<{ assignment: Assignment }>("/api/v1/assignments", {
    method: "POST",
    body: formData,
  });
  return assignmentSchema.parse(result.assignment);
}

export async function planAnswer(assignmentId: string, questionId: string, answerText: string): Promise<PlacementPlan> {
  const result = await request<{ plan: PlacementPlan }>(`/api/v1/assignments/${assignmentId}/plan`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ questionId, answerText }),
  });
  return placementPlanSchema.parse(result.plan);
}

export async function commitAnswer(assignmentId: string, planToken: string): Promise<Assignment> {
  const result = await request<{ assignment: Assignment }>(`/api/v1/assignments/${assignmentId}/commit`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ planToken }),
  });
  return assignmentSchema.parse(result.assignment);
}

export async function exportAssignment(assignmentId: string): Promise<Blob> {
  const response = await fetch(`/api/v1/assignments/${assignmentId}/export`, { credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: { message: "Export failed." } }));
    throw new Error(body.error?.message ?? "Export failed.");
  }
  return response.blob();
}
