import { expect, type Page, test } from "@playwright/test";

/** The seeded firm — mirrors `tests/e2e/serve.py`. Nothing here is a real firm or a real matter. */
export const TENANT = "cabinet";
export const EMAIL = "avocat@cabinet.test";
export const PASSWORD = "motdepasse-e2e";
export const MATTER = "affaire-a";
export const DISPLAY_NAME = "Me Durand";

/**
 * Sign in through the product's own screen, never by planting a session cookie.
 *
 * The login form is part of what these tests exist to exercise, and a fixture that bypassed it
 * would make every later assertion conditional on a path nothing checks — which is how a suite ends
 * up green over a product nobody can get into.
 */
export async function signIn(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Cabinet").fill(TENANT);
  await page.getByLabel("Courriel").fill(EMAIL);
  await page.getByLabel("Mot de passe").fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();
  // The header carries the DISPLAY NAME and the wall, never the e-mail — the first browser run
  // asserted the e-mail and was wrong about the product, which is the point of running one.
  await expect(page.getByText(DISPLAY_NAME)).toBeVisible({ timeout: 20_000 });
}

/**
 * Open a *matter*'s ranked table.
 *
 * Signing in lands on the DEPOSIT form; the matters are a section below it («&nbsp;Mes
 * dossiers&nbsp;»), and «&nbsp;Cockpit&nbsp;» is the admin panel, not a matters zone. The home
 * screen FR-27 and story 2.11 describe — the worklist on top, the matters below it as navigation —
 * is not built. Recorded here rather than worked around silently: this fixture is the shortest
 * honest description of what a lawyer has to do today.
 */
export async function openMatter(page: Page): Promise<void> {
  await page.getByRole("heading", { name: "Mes dossiers" }).scrollIntoViewIfNeeded();
  await page.getByRole("link", { name: "Ouvrir le classement…" }).first().click();
}

export { expect, test };
