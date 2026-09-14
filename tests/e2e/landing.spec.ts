import AxeBuilder from "@axe-core/playwright";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { createSample } from "./support/app";

const repositoryRoot = fileURLToPath(new URL("../../", import.meta.url));
const supportedWorksheet = join(
  repositoryRoot,
  "backend",
  "tests",
  "corpus",
  "01-biology-polished.pdf",
);

test("landing CTA reaches the real application without loading document or Realtime code", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));

  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Think it. Say it. Put it on the page.",
    }),
  ).toBeVisible();
  expect(
    requests.filter((url) => /(?:pdfium|embedpdf|realtime)/iu.test(url)),
  ).toEqual([]);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  await page
    .getByRole("link", { name: /Try Claros/ })
    .first()
    .click();
  await expect(page).toHaveURL("/app");
  await expect(
    page.getByRole("heading", { level: 1, name: "Bring in a worksheet." }),
  ).toBeVisible();
});

test("sample selection creates a real assignment and opens one conversation", async ({
  page,
}) => {
  const created = await createSample(page);
  await page.getByRole("button", { name: "Looks right. Start" }).click();

  await expect(page).toHaveURL(`/app/${created.assignment_id}`);
  await expect(page.getByLabel("Conversation workspace")).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Message Claros" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Proposed answer" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start a guided conversation" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Start answering" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("img", { name: /original worksheet excerpt/i }),
  ).toBeVisible();
});

test("supported upload uses the same real assignment pipeline", async ({
  page,
}) => {
  await page.goto("/app");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v2/assignments",
  );
  await page
    .getByLabel("Choose a PDF worksheet")
    .setInputFiles(supportedWorksheet);
  const response = await createdResponse;
  expect(response.status()).toBe(201);
  const created = (await response.json()) as { assignment_id: string };

  await expect(
    page.getByRole("heading", { level: 1, name: "Check your questions." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Looks right. Start" }).click();
  await expect(page).toHaveURL(`/app/${created.assignment_id}`);
  await expect(page.getByLabel("Conversation workspace")).toBeVisible();
});

test("mobile worksheet dialog restores focus, reflows, and remains accessible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const created = await createSample(page);
  await page.getByRole("button", { name: "Looks right. Start" }).click();
  await expect(page).toHaveURL(`/app/${created.assignment_id}`);

  const viewWorksheet = page
    .locator(".v2-mobile-document-action")
    .getByRole("button", { name: "View worksheet" });
  await viewWorksheet.focus();
  await viewWorksheet.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("status")).toContainText(
    "Original worksheet ready. Read only.",
  );
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(viewWorksheet).toBeFocused();
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
});
