import { expect, type Page } from "@playwright/test";

export async function createSample(page: Page) {
  await page.goto("/app");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v2/assignments",
  );
  await page.getByRole("button", { name: "Try the biology sample" }).click();
  const response = await createdResponse;
  expect(response.status()).toBe(201);
  const created = (await response.json()) as {
    assignment_id: string;
    source: { sha256: string };
    questions: Array<{ question_id: string; prompt: string }>;
  };
  await expect(
    page.getByRole("heading", { level: 1, name: "Check your questions." }),
  ).toBeVisible();
  return created;
}

export async function openSampleWorkspace(page: Page) {
  const created = await createSample(page);
  await page.getByRole("button", { name: "Looks right — Start" }).click();
  await expect(page).toHaveURL(`/app/${created.assignment_id}`);
  await expect(page.getByLabel("Conversation workspace")).toBeVisible();
  return created;
}
