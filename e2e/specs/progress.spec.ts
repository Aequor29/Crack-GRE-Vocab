import { expect, signIn, signOut, signUp, test } from "../fixtures/learner.js";
import { expectOneAnswer, rememberWord, startStudy } from "../fixtures/study.js";

test("a new learner sees empty progress and gains a study day after answering", async ({
  signedInPage: page,
  learner,
}) => {
  await expect(page.getByText("0 of 3,034 words seen", { exact: true })).toBeVisible();
  await expect(page.getByText("0 answers", { exact: true })).toBeVisible();
  await expect(page.getByText("0 day streak", { exact: true })).toBeVisible();
  await expect(page.getByText("No review history yet", { exact: true })).toBeVisible();
  await startStudy(page);
  await rememberWord(page);
  await expectOneAnswer(page);
  await expect(page.getByText("1 day streak", { exact: true })).toBeVisible();
  // An initial learning answer is not counted as a review-phase recall answer.
  await expect(page.getByText("No review history yet", { exact: true })).toBeVisible();
  await signOut(page);
  await signIn(page, learner);
  await expect(page.getByText("1 answers", { exact: true })).toBeVisible();
  await expect(page.getByText("1 day streak", { exact: true })).toBeVisible();
});

test("switching learners never exposes the previous learner's progress or active session", async ({
  signedInPage: page,
  learner,
}) => {
  await startStudy(page);
  await rememberWord(page);
  await expectOneAnswer(page);
  await signOut(page);
  await signUp(page, { ...learner, email: `other-${learner.email}` });
  await expect(page.getByText("0 of 3,034 words seen", { exact: true })).toBeVisible();
  await expect(page.getByText("0 answers", { exact: true })).toBeVisible();
  await expect(page.getByText("0 day streak", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Start studying", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start session", exact: true })).toBeVisible();
  await signOut(page);
  await signIn(page, learner);
  await expect(page.getByText("1 answers", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue studying", exact: true })).toBeVisible();
});
