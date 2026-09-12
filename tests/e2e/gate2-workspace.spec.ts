import AxeBuilder from "@axe-core/playwright";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";
import { inspectPdf } from "../e2e-gate3/support/server";
import { createSample } from "./support/app";

const questionOne = "Why do plants need sunlight?";
const questionTwo = "How does sunlight help a plant make food?";

async function openWorkspace(page: Page, search = "?replay=controls") {
  const created = await createSample(page);
  await page.goto(`/app/${created.assignment_id}${search}`);
  await expect(
    page.getByRole("heading", { level: 1, name: questionOne }),
  ).toBeVisible();
  return created;
}

async function enterReview(page: Page, answer: string) {
  await page.getByRole("textbox", { name: "Proposed answer" }).fill(answer);
  await page.getByRole("button", { name: "Review answer" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Review your exact answer" }),
  ).toBeVisible();
  await expect(page.getByText(answer, { exact: true })).toBeVisible();
}

async function sendMessage(page: Page, message: string) {
  const editor = page.getByRole("textbox", { name: "Message Claros" });
  await editor.fill(message);
  await page.getByRole("button", { name: "Send to Claros" }).click();
}

test("deterministic Realtime replay preserves capture intent, typed continuity, and question drafts", async ({
  page,
}) => {
  await openWorkspace(page);
  const draft = "Plants use light energy to make food.";
  await page.getByRole("textbox", { name: "Proposed answer" }).fill(draft);

  await page.getByRole("button", { name: "Start speaking" }).click();
  const stopListening = page.getByRole("button", { name: "Stop listening" });
  await expect(stopListening).toBeVisible();
  await expect(
    page.getByLabel("Voice controls").getByRole("status"),
  ).toContainText("Listening");

  await sendMessage(page, "Can you give me one short hint?");
  await expect(
    page.getByLabel("Voice controls").getByRole("status"),
  ).toContainText("Thinking");
  await expect(stopListening).toBeVisible();
  await expect(
    page.getByLabel("Voice controls").getByRole("status"),
  ).toContainText("Speaking");
  await expect(stopListening).toBeVisible();

  await stopListening.click();
  await expect(
    page.getByRole("button", { name: "Start speaking" }),
  ).toBeVisible();
  await sendMessage(page, "Go to question 2");
  await expect(
    page.getByRole("heading", { level: 1, name: questionTwo }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Proposed answer" }),
  ).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Start speaking" }),
  ).toBeVisible();

  await sendMessage(page, "Go to question 1");
  await expect(
    page.getByRole("heading", { level: 1, name: questionOne }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Proposed answer" }),
  ).toHaveValue(draft);
  await expect(
    page.getByRole("button", { name: "Start speaking" }),
  ).toBeVisible();
});

test("disconnect preserves the question-bound draft and hands control to typing", async ({
  page,
}) => {
  await openWorkspace(page, "?replay=disconnect");
  const draft = "Plants need sunlight because my current thought is";
  const completed =
    "Plants need sunlight because it supplies energy for photosynthesis.";
  const candidate = page.getByRole("textbox", { name: "Proposed answer" });
  await candidate.fill(draft);

  await page.getByRole("button", { name: "Start speaking" }).click();
  await page.getByRole("button", { name: "Stop listening" }).click();
  await expect(
    page.getByLabel("Voice controls").getByRole("status"),
  ).toContainText("Connection lost");
  await expect(candidate).toHaveValue(draft);
  await page.getByRole("button", { name: "Continue by typing" }).click();
  await expect(candidate).toHaveValue(draft);
  await page.getByRole("button", { name: "Start speaking" }).click();
  await page.getByRole("button", { name: "Stop listening" }).click();
  await expect(
    page.getByLabel("Voice controls").getByRole("status"),
  ).toContainText("Connection lost");
  await page.getByRole("button", { name: "Retry voice" }).click();
  await expect(
    page.getByLabel("Voice controls").getByRole("status"),
  ).toContainText("Ready");
  await expect(
    page.getByRole("button", { name: "Start speaking" }),
  ).toBeVisible();
  await expect(candidate).toHaveValue(draft);
  await candidate.fill(completed);
  await enterReview(page, completed);
});

test("review is exact, stale approval is invalidated by revision, and acknowledgement stays conversational", async ({
  page,
}) => {
  const created = await openWorkspace(page);
  const original =
    "Plants need sunlight because chlorophyll captures energy for photosynthesis.";
  const revision =
    "Plants capture sunlight and use that energy to make glucose during photosynthesis.";
  const confirmationRequests: string[] = [];
  const confirmationStatuses: number[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/confirm")) {
      confirmationRequests.push(request.url());
    }
  });
  page.on("response", (response) => {
    if (
      response.request().method() === "POST" &&
      response.url().endsWith("/confirm")
    ) {
      confirmationStatuses.push(response.status());
    }
  });
  await page.getByRole("button", { name: "Start speaking" }).click();
  const firstReviewResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/review"),
  );
  await enterReview(page, original);
  const firstReview = (await (await firstReviewResponse).json()) as {
    version: number;
    review_token: string;
    candidate: { candidate_id: string; candidate_version: number };
  };
  await expect(
    page.getByRole("button", { name: "Stop listening" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      /answer (?:fits on the original worksheet|will appear on an attached answer page)/i,
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Use this exact answer" }).click();
  await expect(
    page.getByRole("heading", { name: /Answer added/ }),
  ).toBeVisible();
  expect(confirmationRequests).toHaveLength(1);
  await expect(page.getByLabel("Conversation workspace")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Stop listening" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Edit answer" }).click();
  await expect(
    page.getByRole("textbox", { name: "Proposed answer" }),
  ).toHaveValue(original);
  const staleAttempt = await page.evaluate(
    async ({ assignmentId, questionId, review }) => {
      const response = await fetch(
        `/api/v2/assignments/${assignmentId}/questions/${questionId}/confirm`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            assignment_version: review.version,
            review_token: review.review_token,
            candidate_id: review.candidate.candidate_id,
            candidate_version: review.candidate.candidate_version,
          }),
        },
      );
      return { status: response.status, body: await response.json() };
    },
    {
      assignmentId: created.assignment_id,
      questionId: created.questions[0].question_id,
      review: firstReview,
    },
  );
  expect(staleAttempt.status).toBe(409);
  expect(staleAttempt.body.error.code).toMatch(/review|version|candidate/iu);
  await expect.poll(() => confirmationStatuses).toEqual([200, 409]);

  await enterReview(page, revision);
  await page.getByRole("button", { name: "Use this exact answer" }).click();
  await expect(page.getByText(revision, { exact: true })).toBeVisible();
  expect(confirmationRequests).toHaveLength(3);
  await expect.poll(() => confirmationStatuses).toEqual([200, 409, 200]);
});

test("spoken confirmation replay accepts only the narrow exact-review command and approves once", async ({
  page,
}) => {
  await openWorkspace(page);
  const answer = "Plants use sunlight as energy to make their own food.";
  const confirmationRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/confirm")) {
      confirmationRequests.push(request.url());
    }
  });
  await page.getByRole("button", { name: "Start speaking" }).click();
  await enterReview(page, answer);

  for (const rejected of [
    "okay",
    "Don't use this exact answer",
    "Use this exact answer?",
    "Please use this exact answer",
  ]) {
    await page.evaluate((phrase) => {
      const url = new URL(window.location.href);
      url.searchParams.set("confirmation", phrase);
      window.history.replaceState({}, "", url);
    }, rejected);
    await page.getByRole("button", { name: "Hear it" }).click();
    await expect(
      page.getByRole("heading", { name: "Review your exact answer" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Hear it" })).toBeVisible();
    expect(confirmationRequests).toHaveLength(0);
  }

  await page.evaluate(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("confirmation", "Use this exact answer!");
    window.history.replaceState({}, "", url);
  });
  await page.getByRole("button", { name: "Hear it" }).click();
  await expect(
    page.getByRole("heading", { name: /Answer added/ }),
  ).toBeVisible();
  expect(confirmationRequests).toHaveLength(1);
  await expect(page.getByText(answer, { exact: true })).toBeVisible();
  await expect(
    page.getByText("Use this exact answer!", { exact: true }),
  ).not.toBeVisible();
});

test("OpenPDF export contains confirmed answers only and preserves the source", async ({
  page,
}, testInfo) => {
  const created = await openWorkspace(page);
  const confirmed =
    "Plants need sunlight because light provides energy for photosynthesis.";
  const unconfirmed = "This second-question draft must not be published.";
  const sourceBefore = await page.evaluate(async (assignmentId) => {
    const response = await fetch(`/api/v2/assignments/${assignmentId}/source`);
    return Array.from(new Uint8Array(await response.arrayBuffer()));
  }, created.assignment_id);
  expect(
    createHash("sha256").update(Uint8Array.from(sourceBefore)).digest("hex"),
  ).toBe(created.source.sha256);

  await enterReview(page, confirmed);
  await page.getByRole("button", { name: "Use this exact answer" }).click();
  await page.getByRole("button", { name: "Continue to Question 2" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: questionTwo }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Proposed answer" })
    .fill(unconfirmed);
  await page.getByRole("link", { name: "Review answers" }).click();
  await expect(
    page.getByRole("heading", { name: "Review answers" }),
  ).toBeVisible();
  await expect(page.locator(".v2-task").getByRole("status")).toContainText(
    "1 of 3 answered. Unanswered questions will stay blank.",
  );

  await page.getByRole("button", { name: "Download completed PDF" }).click();
  await expect(
    page.getByRole("heading", { name: "Your completed PDF is ready" }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download completed PDF" }).click();
  const download = await downloadPromise;
  const downloadPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(downloadPath);
  const bytes = await readFile(downloadPath);
  expect(bytes.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  const inspected = inspectPdf(downloadPath);
  expect(inspected.warnings).toEqual([]);
  expect(inspected.pageCount).toBeGreaterThanOrEqual(1);
  expect(inspected.text).toContain(confirmed);
  expect(inspected.text).not.toContain(unconfirmed);

  const sourceAfter = await page.evaluate(async (assignmentId) => {
    const response = await fetch(`/api/v2/assignments/${assignmentId}/source`);
    return Array.from(new Uint8Array(await response.arrayBuffer()));
  }, created.assignment_id);
  expect(
    createHash("sha256").update(Uint8Array.from(sourceAfter)).digest("hex"),
  ).toBe(created.source.sha256);
});

test("workspace supports keyboard-only review and has no automated axe violations", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openWorkspace(page);
  const answer = "Plants use light energy to make glucose.";
  const editor = page.getByRole("textbox", { name: "Proposed answer" });
  await editor.focus();
  await page.keyboard.insertText(answer);
  const review = page.getByRole("button", { name: "Review answer" });
  await review.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Review your exact answer" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const confirm = page.getByRole("button", { name: "Use this exact answer" });
  await confirm.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: /Answer added/ }),
  ).toBeVisible();
});
