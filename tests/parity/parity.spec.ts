import { expect, test, type Page } from "@playwright/test";
import { maintainedUiRoutes } from "../../packages/migration-contract/src/index";

const adminEmail = process.env.PARITY_ADMIN_EMAIL ?? "alex.rivera@boardtpl.local";
const adminPassword = process.env.PARITY_ADMIN_PASSWORD ?? "ChangeMe!123";

async function signInAsAdmin(page: Page): Promise<void> {
  await page.goto("/auth/signin?returnTo=%2Fplayer");
  await page.getByLabel("Email").fill(adminEmail);
  await page.locator('input[autocomplete="current-password"]').first().fill(adminPassword);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await page.waitForURL("**/player");
}

async function waitForParityRouteReady(page: Page, route: (typeof maintainedUiRoutes)[number]): Promise<void> {
  await expect(page.getByText(route.parityMarker, { exact: false }).first()).toBeVisible();

  if (route.label === "Browse" || route.label === "Public Studio") {
    await expect(page.getByText("Lantern Drift", { exact: false }).first()).toBeVisible();
  }
}

test("public route smoke markers remain reachable", async ({ page }) => {
  const publicRoutes = maintainedUiRoutes.filter((route) => route.access === "public");

  for (const route of publicRoutes) {
    await page.goto(route.path);
    await waitForParityRouteReady(page, route);
  }
});

test("authenticated route smoke markers remain reachable", async ({ page }) => {
  await signInAsAdmin(page);

  const authenticatedRoutes = maintainedUiRoutes.filter((route) => route.access !== "public");
  for (const route of authenticatedRoutes) {
    await page.goto(route.path);
    await waitForParityRouteReady(page, route);
  }
});

test("public route screenshots match the committed baseline", async ({ page }) => {
  const targets = maintainedUiRoutes.filter((route) => route.access === "public");

  for (const route of targets) {
    await page.goto(route.path);
    await waitForParityRouteReady(page, route);
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
    await waitForParityRouteReady(page, route);
    await expect(page).toHaveScreenshot(`${route.label.toLowerCase().replace(/\s+/g, "-")}.png`, {
      animations: "disabled",
      fullPage: true,
      maxDiffPixelRatio: 0.02
    });
  }
});
