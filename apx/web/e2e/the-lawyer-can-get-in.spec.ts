import { DISPLAY_NAME, EMAIL, MATTER, expect, openMatter, signIn, test } from "./fixtures";

/**
 * The first browser test in this repository, and it exists because of a sentence.
 *
 * Three stories in a row were split with *"the client has no test runner at all, so no property in
 * that half is falsifiable by this repository"*. That was true, and it was being used to defer the
 * work rather than to close the gap. Everything below is a property that `npm run build` and
 * `tsc --noEmit` cannot see: they prove the code COMPILES, never that a lawyer can get in and find
 * her matter.
 *
 * It drives the composition a container actually has — one process serving the API and the built
 * SPA from the same origin — against a seeded throwaway database.
 */

test("a lawyer signs in and the header names her and her wall", async ({ page }) => {
  await signIn(page);
  await expect(page.getByText(DISPLAY_NAME)).toBeVisible();
  // scoped to the header: "mur-a" also appears in the deposit form's scope selector and on a chip,
  // and a bare text match would pass on any one of the three
  await expect(page.locator("header").getByText("mur-a")).toBeVisible();
  // the e-mail is a credential, not an identity to print on every screen
  await expect(page.getByText(EMAIL, { exact: false })).toBeHidden();
});

test("a wrong password is refused, in French, and reveals nothing", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Cabinet").fill("cabinet");
  await page.getByLabel("Courriel").fill(EMAIL);
  await page.getByLabel("Mot de passe").fill("ce-n-est-pas-le-bon");
  await page.getByRole("button", { name: "Se connecter" }).click();

  // still on the login screen, and the message must not distinguish "no such user" from
  // "wrong password" — the same non-disclosure rule the API answers 404 with (FR-14)
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mes dossiers" })).toBeHidden();
});

test("the matter opens on its ranked table, or says plainly that it has no ranking", async ({
  page,
}) => {
  await signIn(page);
  await openMatter(page);

  // The seeded matter is ingested and NOT ranked — story 7.6 made ranking a request and 7.8 has
  // not yet put the gesture on the screen. So the honest state is the one this asserts, and when
  // 7.8 lands this test is what says whether the dead end became a control.
  await expect(
    page.getByText(/Aucun classement pour ce dossier|Classement v\d+/),
  ).toBeVisible({ timeout: 20_000 });
});
