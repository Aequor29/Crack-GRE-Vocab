import { expect, signIn, signOut, test } from "../fixtures/learner.js";
import { passwordResetLink } from "../fixtures/mail.js";

test("a learner can create an account and restore their session after a reload", async ({
  signedInPage: page,
  learner,
}) => {
  await page.getByRole("link", { name: "Manage account" }).click();
  await expect(page.getByText(learner.email, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText(learner.email, { exact: true })).toBeVisible();
});

test("a password-reset email restores access with a new password and invalidates existing sessions", async ({
  signedInPage: page,
  learner,
  browser,
  baseURL,
}) => {
  const otherContext = await browser.newContext({ baseURL });
  try {
    const otherSession = await otherContext.newPage();
    await signIn(otherSession, learner);
    await otherSession.goto("/account");
    await expect(otherSession.getByText(learner.email, { exact: true })).toBeVisible();

    await page.goto("/forgot-password");
    await page.getByLabel("Email", { exact: true }).fill(learner.email);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText(
      "If an account can be recovered",
    );
    const resetLink = await passwordResetLink(learner.email);
    const newPassword = "renewed-recall-forest-853";
    await page.goto(resetLink);
    await page.getByLabel("New password", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText(
      "Password reset complete",
    );

    await otherSession.reload();
    await expect(otherSession).toHaveURL(/\/sign-in$/);
    await page.goto("/account");
    await expect(page).toHaveURL(/\/sign-in$/);

    await page.getByLabel("Email", { exact: true }).fill(learner.email);
    await page.getByLabel("Password", { exact: true }).fill(learner.password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
    await signIn(page, { ...learner, password: newPassword });

    await page.goto(resetLink);
    await page.getByLabel("New password", { exact: true }).fill("another-password-river-294");
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("invalid or has expired");
  } finally {
    await otherContext.close();
  }
});

test("signing out protects account, dashboard, and study until the learner signs in again", async ({
  signedInPage: page,
  learner,
}) => {
  await signOut(page);
  for (const path of ["/account", "/dashboard", "/study"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/sign-in$/);
  }
  await signIn(page, learner);
  await page.goto("/account");
  await expect(page.getByText(learner.email, { exact: true })).toBeVisible();
});
