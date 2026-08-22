import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("landing page exposes the supported worksheet promise", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /The answer is yours\.\s*Getting it onto the page can be easier\./ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open workspace/ }).first()).toBeVisible();
  await expect(page.getByText("One clear answer space", { exact: true }).last()).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.locator(".review-card").evaluate((element) => Promise.all(element.getAnimations().map((animation) => animation.finished)));
  const screenshot = testInfo.outputPath("landing-desktop.png");
  await page.screenshot({ path: screenshot, fullPage: true });
  await testInfo.attach("landing-desktop", { path: screenshot, contentType: "image/png" });
});

test("mobile landing keeps the answer story in a readable sequence", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.locator(".voice-chip strong")).toHaveText("Talk it through");
  await expect(page.locator(".voice-chip strong")).toBeVisible();
  await expect(page.getByRole("img", { name: /Question 2 moves from optional voice discussion/ })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  const screenshot = testInfo.outputPath("landing-mobile.png");
  await page.screenshot({ path: screenshot, fullPage: true });
  await testInfo.attach("landing-mobile", { path: screenshot, contentType: "image/png" });
});

test("desktop workspace keeps export gated and exposes a worksheet transcript", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.goto("/app");
  await page.getByRole("button", { name: "Try sample worksheet" }).click();

  await expect(page.locator(".question-column")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: /Export/ })).toHaveCount(0);
  await expect(page.getByRole("region", { name: /transcript/i })).toContainText("Question 1");

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  const screenshot = testInfo.outputPath("workspace-desktop.png");
  await page.screenshot({ path: screenshot, fullPage: true });
  await testInfo.attach("workspace-desktop", { path: screenshot, contentType: "image/png" });
});

test("mobile workspace switches cleanly between worksheet and answer", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/app");
  await page.getByRole("button", { name: "Try sample worksheet" }).click();

  const viewSwitch = page.getByRole("group", { name: "Workspace view" });
  await expect(viewSwitch).toBeVisible({ timeout: 15_000 });
  const worksheetSwitch = viewSwitch.getByRole("button", { name: "Worksheet", exact: true });
  const answerSwitch = viewSwitch.getByRole("button", { name: "Answer", exact: true });
  await expect(worksheetSwitch).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".document-column")).toBeVisible();
  await expect(page.getByLabel("Final answer")).toHaveCount(0);
  await expect(page.locator(".pdf-page-wrap canvas")).toBeVisible({ timeout: 15_000 });
  const worksheetOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(worksheetOverflow).toBeLessThanOrEqual(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  const worksheetScreenshot = testInfo.outputPath("workspace-mobile-worksheet.png");
  await page.screenshot({ path: worksheetScreenshot, fullPage: true });
  await testInfo.attach("workspace-mobile-worksheet", { path: worksheetScreenshot, contentType: "image/png" });

  await answerSwitch.click();
  await expect(answerSwitch).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Final answer")).toBeVisible();
  await expect(page.locator(".document-column")).toHaveCount(0);
  await page.evaluate(() => window.scrollTo(0, 0));

  for (const control of [page.getByRole("link", { name: "Exit" }), worksheetSwitch, answerSwitch, page.getByRole("button", { name: "Talk it through" }), page.getByRole("button", { name: "Dictate final answer" })]) {
    const box = await control.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    expect(box?.width).toBeGreaterThanOrEqual(44);
  }
  const answerOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(answerOverflow).toBeLessThanOrEqual(0);

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  const answerScreenshot = testInfo.outputPath("workspace-mobile-answer.png");
  await page.screenshot({ path: answerScreenshot, fullPage: true });
  await testInfo.attach("workspace-mobile-answer", { path: answerScreenshot, contentType: "image/png" });
});
