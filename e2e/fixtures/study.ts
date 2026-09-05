import { expect, type Page } from "@playwright/test";

export async function startStudy(page: Page, newWords = 2) {
  await page.goto("/study");
  const target = page.getByRole("slider", { name: "New-word target" });
  await target.focus();
  await target.press("Home");
  for (let index = 0; index < newWords; index += 1) {
    await target.press("ArrowRight");
  }
  await expect(target).toHaveValue(String(newWords));
  await page.getByRole("button", { name: "Start session", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reveal meaning" })).toBeVisible();
}

export async function rememberWord(page: Page) {
  await page.getByRole("button", { name: "Reveal meaning" }).click();
  await page.getByRole("button", { name: "Remembered", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reveal meaning" })).toBeVisible();
}

export async function expectOneAnswer(page: Page) {
  await page.goto("/dashboard");
  await expect(page.getByText("1 answers", { exact: true })).toBeVisible();
  await expect(page.getByText("1 of 3,034 words seen", { exact: true })).toBeVisible();
}
