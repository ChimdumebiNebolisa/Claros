import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { inspectPdf } from "../e2e-gate3/support/server";
import { createSample } from "./support/app";

const repositoryRoot = fileURLToPath(new URL("../../", import.meta.url));
const worksheetPath = join(
  repositoryRoot,
  "backend",
  "tests",
  "corpus",
  "01-biology-polished.pdf",
);

type Setup = {
  version: number;
  verified: boolean;
  provenance: "detected" | "student_corrected";
  pages: Array<{
    page_number: number;
    width_mpt: number;
    height_mpt: number;
  }>;
  questions: Array<{
    question_id: string;
    prompt: string;
    instruction: string | null;
  }>;
};

type Blocks = {
  blocks: Array<{
    block_id: string;
    exact_text: string;
    reading_order: number;
    selected_question_ids: string[];
    region: {
      x_mpt: number;
      y_mpt: number;
      width_mpt: number;
      height_mpt: number;
    };
  }>;
};

async function readSetup(
  page: import("@playwright/test").Page,
  assignmentId: string,
) {
  return page.evaluate(async (id) => {
    const response = await fetch(
      `/api/v2/assignments/${encodeURIComponent(id)}/question-setup`,
    );
    return (await response.json()) as Setup;
  }, assignmentId);
}

test("uploaded worksheet remains visible while real analysis is pending", async ({
  page,
}, testInfo) => {
  await page.route("**/api/v2/assignments", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2_000));
    await route.continue();
  });
  await page.goto("/app");
  await page.getByLabel("Choose a PDF worksheet").setInputFiles(worksheetPath);
  await expect(
    page.getByRole("heading", { level: 1, name: "Checking your worksheet" }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Worksheet preview while checking"),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("checking-worksheet.png"),
    fullPage: true,
  });
  await expect(
    page.getByRole("heading", { level: 1, name: "Check your questions." }),
  ).toBeVisible();
});

test("real source correction reaches answering and a validated OpenPDF export", async ({
  page,
}, testInfo) => {
  const created = await createSample(page);
  const setupBefore = await readSetup(page, created.assignment_id);
  expect(setupBefore).toMatchObject({
    verified: false,
    provenance: "detected",
  });
  await page.screenshot({
    path: testInfo.outputPath("question-check-desktop.png"),
    fullPage: true,
  });

  const rejected = await page.evaluate(
    async ({ id, version, questionId }) => {
      const response = await fetch(
        `/api/v2/assignments/${encodeURIComponent(id)}/question-setup`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            assignment_version: version,
            operation: {
              kind: "replace",
              question_id: questionId,
              page_number: 1,
              block_ids: ["not-source-evidence"],
            },
          }),
        },
      );
      return { status: response.status, body: await response.json() };
    },
    {
      id: created.assignment_id,
      version: setupBefore.version,
      questionId: setupBefore.questions[0].question_id,
    },
  );
  expect(rejected).toMatchObject({
    status: 422,
    body: {
      error: { code: "invalid_question_setup", recoverable: true },
    },
  });

  await page.getByRole("button", { name: "Something looks wrong" }).click();
  await page.getByRole("button", { name: "Fix selection" }).first().click();
  const firstQuestion = setupBefore.questions[0];
  const blocks = await page.evaluate(async (id) => {
    const response = await fetch(
      `/api/v2/assignments/${encodeURIComponent(id)}/pages/1/question-blocks`,
    );
    return (await response.json()) as Blocks;
  }, created.assignment_id);
  const promptBlock = blocks.blocks.find(
    (block) => block.exact_text === firstQuestion.prompt,
  );
  const supplementalBlock = blocks.blocks
    .filter((block) =>
      block.selected_question_ids.every(
        (questionId) => questionId === firstQuestion.question_id,
      ),
    )
    .filter((block) => block.exact_text.length > 10)
    .filter((block) => block.exact_text !== firstQuestion.prompt)
    .sort(
      (left, right) =>
        Math.abs(left.reading_order - (promptBlock?.reading_order ?? 0)) -
        Math.abs(right.reading_order - (promptBlock?.reading_order ?? 0)),
    )[0];
  expect(promptBlock).toBeTruthy();
  expect(supplementalBlock).toBeTruthy();

  const overlay = page.getByLabel("Select question text on worksheet");
  const overlayBox = await overlay.boundingBox();
  const pageSize = setupBefore.pages[0];
  expect(overlayBox).toBeTruthy();
  if (!overlayBox || !promptBlock || !pageSize) {
    throw new Error("Question selection geometry was unavailable");
  }
  expect(overlayBox.y).toBeGreaterThanOrEqual(0);
  expect(overlayBox.width / overlayBox.height).toBeCloseTo(
    pageSize.width_mpt / pageSize.height_mpt,
    2,
  );
  const startX =
    overlayBox.x +
    ((promptBlock.region.x_mpt - 4_000) / pageSize.width_mpt) *
      overlayBox.width;
  const startY =
    overlayBox.y +
    ((promptBlock.region.y_mpt - 4_000) / pageSize.height_mpt) *
      overlayBox.height;
  const endX =
    overlayBox.x +
    ((promptBlock.region.x_mpt + promptBlock.region.width_mpt + 4_000) /
      pageSize.width_mpt) *
      overlayBox.width;
  const endY =
    overlayBox.y +
    ((promptBlock.region.y_mpt + promptBlock.region.height_mpt + 4_000) /
      pageSize.height_mpt) *
      overlayBox.height;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(endX, endY, { steps: 8 });
  await page.screenshot({
    path: testInfo.outputPath("drag-selection-state.png"),
    fullPage: true,
  });
  await page.mouse.up();
  await expect(
    page.getByRole("checkbox", { name: firstQuestion.prompt, exact: true }),
  ).toBeChecked();

  const instruction = page.getByRole("checkbox", {
    name: supplementalBlock!.exact_text,
    exact: true,
  });
  await instruction.focus();
  await page.keyboard.press("Space");
  await expect(instruction).toBeChecked();
  await page.screenshot({
    path: testInfo.outputPath("keyboard-block-selection.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Check selected text" }).click();
  const correctionPreview = page
    .getByRole("status")
    .filter({ hasText: "Selected question" });
  await expect(correctionPreview).toContainText(firstQuestion.prompt);
  await expect(correctionPreview).toContainText(supplementalBlock!.exact_text);
  await page.screenshot({
    path: testInfo.outputPath("exact-selected-text-confirmation.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Save question" }).click();

  const setupAfter = await readSetup(page, created.assignment_id);
  expect(setupAfter).toMatchObject({
    verified: false,
    provenance: "student_corrected",
  });
  expect(setupAfter.questions[0].question_id).toBe(
    setupBefore.questions[0].question_id,
  );
  expect(setupAfter.questions.map((question) => question.question_id)).toEqual(
    setupBefore.questions.map((question) => question.question_id),
  );
  const correctedPrompt = [promptBlock!, supplementalBlock!]
    .sort((left, right) => left.reading_order - right.reading_order)
    .map((block) => block.exact_text)
    .join("\n");
  expect(setupAfter.questions[0].prompt).toBe(correctedPrompt);

  await page.getByRole("button", { name: "Review changes" }).click();
  await page.getByRole("button", { name: "Looks right. Start" }).click();
  await expect(page).toHaveURL(`/app/${created.assignment_id}`);
  const activeQuestion = page.getByRole("heading", { level: 1 });
  await expect(activeQuestion).toContainText(firstQuestion.prompt);
  await expect(activeQuestion).toContainText(supplementalBlock!.exact_text);

  const answer =
    "Plants need sunlight because its energy powers photosynthesis in their cells.";
  await page.getByRole("textbox", { name: "Proposed answer" }).fill(answer);
  await page.getByRole("button", { name: "Review answer" }).click();
  await expect(page.getByText(answer, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Use this exact answer" }).click();
  await page.getByRole("link", { name: "Review answers" }).click();
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
  const publication = inspectPdf(downloadPath);
  expect(publication.warnings).toEqual([]);
  expect(publication.text).toContain(answer);
});

test("mobile correction is task-first, keyboard complete, and accessible", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await createSample(page);
  const task = page.getByRole("heading", { name: "Check your questions." });
  const worksheet = page.getByText("Original PDF · read only");
  expect((await task.boundingBox())!.y).toBeLessThan(
    (await worksheet.boundingBox())!.y,
  );
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      ),
    )
    .toBeLessThanOrEqual(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("question-check-mobile.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Something looks wrong" }).click();
  await page.getByRole("button", { name: "Fix selection" }).first().click();
  await expect(
    page.getByLabel("Question text selection instructions"),
  ).toBeFocused();
  const firstCheckbox = page.getByRole("checkbox").first();
  await page.keyboard.press("Tab");
  await expect(firstCheckbox).toBeFocused();
  await page.keyboard.press("Space");
  await expect(firstCheckbox).toBeChecked();
  await expect(
    page.getByText(/Drag over the question, tap its text/),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      ),
    )
    .toBeLessThanOrEqual(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("question-correction-mobile.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 640, height: 900 });
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      ),
    )
    .toBeLessThanOrEqual(0);
});
