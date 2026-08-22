import { http, HttpResponse } from "msw";

export const handlers = [
  http.post("/api/v1/assignments", () => HttpResponse.json(
    { error: { code: "document_validation_failed", message: "This worksheet is outside the supported contract." } },
    { status: 422 },
  )),
];
