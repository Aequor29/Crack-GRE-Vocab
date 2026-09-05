import { randomUUID } from "node:crypto";
import { test as base, expect, type Page } from "@playwright/test";

export type Learner = {
  email: string;
  password: string;
  displayName: string;
};

export async function signUp(page: Page, learner: Learner) {
  await page.goto("/sign-up");
  await page.getByLabel("Display name", { exact: true }).fill(learner.displayName);
  await page.getByLabel("Email", { exact: true }).fill(learner.email);
  await page.getByLabel("Password", { exact: true }).fill(learner.password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
}

export async function signIn(page: Page, learner: Learner) {
  await page.goto("/sign-in");
  await page.getByLabel("Email", { exact: true }).fill(learner.email);
  await page.getByLabel("Password", { exact: true }).fill(learner.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
}

export async function signOut(page: Page) {
  await page.goto("/account");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
}

export const test = base.extend<{ learner: Learner; signedInPage: Page }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright requires destructured fixture dependencies.
  learner: async ({}, use) => {
    await use({
      email: `learner-${randomUUID()}@example.test`,
      password: "durable-recall-river-927",
      displayName: "E2E learner",
    });
  },
  signedInPage: async ({ page, learner }, use) => {
    await signUp(page, learner);
    await use(page);
  },
});

export { expect } from "@playwright/test";
