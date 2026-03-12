import { expect, test, type Page } from "@playwright/test";
import { maintainedUiRoutes } from "../../packages/migration-contract/src/index";

const adminEmail = process.env.PARITY_ADMIN_EMAIL ?? "alex.rivera@boardtpl.local";
const adminPassword = process.env.PARITY_ADMIN_PASSWORD ?? "ChangeMe!123";

async function signInAsAdmin(page: Page): Promise<void> {
  await page.goto("/auth/signin?returnTo=%2Fplayer");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/player");
}

test("public route smoke markers remain reachable", async ({ page }) => {
  const publicRoutes = maintainedUiRoutes.filter((route) => route.access === "public");

  for (const route of publicRoutes) {
    await page.goto(route.path);
    await expect(page.getByText(route.parityMarker, { exact: false }).first()).toBeVisible();
  }
});

test("authenticated route smoke markers remain reachable", async ({ page }) => {
  await signInAsAdmin(page);

  const authenticatedRoutes = maintainedUiRoutes.filter((route) => route.access !== "public");
  for (const route of authenticatedRoutes) {
    await page.goto(route.path);
    await expect(page.getByText(route.parityMarker, { exact: false }).first()).toBeVisible();
  }
});

test("public route screenshots match the committed baseline", async ({ page }) => {
  const targets = maintainedUiRoutes.filter((route) => route.access === "public");

  for (const route of targets) {
    await page.goto(route.path);
    await expect(page).toHaveScreenshot(`${route.label.toLowerCase().replace(/\s+/g, "-")}.png`, {
      animations: "disabled",
      fullPage: true,
      maxDiffPixelRatio: 0.02
    });
  }
});

test("authenticated route screenshots match the committed baseline", async ({ page }) => {
  await signInAsAdmin(page);

  const targets = maintainedUiRoutes.filter((route) => route.access !== "public");
  for (const route of targets) {
    await page.goto(route.path);
    await expect(page).toHaveScreenshot(`${route.label.toLowerCase().replace(/\s+/g, "-")}.png`, {
      animations: "disabled",
      fullPage: true,
      maxDiffPixelRatio: 0.02
    });
  }
});
