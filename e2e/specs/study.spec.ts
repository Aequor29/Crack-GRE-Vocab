import { expect, test } from "../fixtures/learner.js";
import { expectOneAnswer, rememberWord, startStudy } from "../fixtures/study.js";

test("a learner can resume a study session, reveal a word, and save a durable answer", async ({
  signedInPage: page,
}) => {
  await startStudy(page);
  const firstWord = await page.getByRole("heading", { level: 2 }).innerText();
  await expect(page.getByRole("button", { name: "Remembered", exact: true })).toBeHidden();
  await page.reload();
  await expect(page.getByRole("heading", { name: firstWord, exact: true })).toBeVisible();
  await rememberWord(page);
  const nextWord = await page.getByRole("heading", { level: 2 }).innerText();
  await expectOneAnswer(page);
  await page.getByRole("link", { name: "Continue studying", exact: true }).click();
  await expect(page.getByRole("heading", { name: nextWord, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: nextWord, exact: true })).toBeVisible();
  await expectOneAnswer(page);
});

for (const recovery of ["retry button", "page reload"] as const) {
  test(`an accepted answer with a lost response is recovered once through ${recovery}`, async ({
    signedInPage: page,
  }) => {
    await startStudy(page);
    let acceptedOutcomeId: string | undefined;
    const answers = "**/api/study/sessions/*/items/*/answer/";
    await page.route(
      answers,
      async (route) => {
        // Let Django commit the real answer, then lose only its acknowledgement.
        const response = await route.fetch();
        expect(response.ok()).toBe(true);
        acceptedOutcomeId = (await response.json()).outcome.id;
        await route.abort("failed");
      },
      { times: 1 },
    );
    await page.getByRole("button", { name: "Reveal meaning" }).click();
    await page.getByRole("button", { name: "Remembered", exact: true }).click();
    await expect(page.getByRole("button", { name: "Retry the same answer" })).toBeVisible();

    const replay = page.waitForResponse(
      (response) => response.url().endsWith("/answer/") && response.request().method() === "POST",
    );
    if (recovery === "retry button") {
      await page.getByRole("button", { name: "Retry the same answer" }).click();
    } else {
      await page.reload();
    }
    const response = await replay;
    expect(response.ok()).toBe(true);
    expect(await response.json()).toMatchObject({
      replayed: true,
      outcome: { id: acceptedOutcomeId },
    });
    await expect(page.getByRole("button", { name: "Reveal meaning" })).toBeVisible();
    await expectOneAnswer(page);
    await page.reload();
    await expect(page.getByText("1 answers", { exact: true })).toBeVisible();
  });
}

test("a real CSRF rejection can be retried without losing or duplicating an answer", async ({
  signedInPage: page,
}) => {
  await startStudy(page);
  await page.route(
    "**/api/study/sessions/*/items/*/answer/",
    async (route) => {
      await route.continue({
        headers: { ...route.request().headers(), "x-csrftoken": "expired-token" },
      });
    },
    { times: 1 },
  );
  const rejection = page.waitForResponse((response) => response.url().endsWith("/answer/"));
  await page.getByRole("button", { name: "Reveal meaning" }).click();
  await page.getByRole("button", { name: "Remembered", exact: true }).click();
  expect((await rejection).status()).toBe(403);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("expired");
  await page.getByRole("button", { name: "Retry the same answer" }).click();
  await expect(page.getByRole("button", { name: "Reveal meaning" })).toBeVisible();
  await expectOneAnswer(page);
});
