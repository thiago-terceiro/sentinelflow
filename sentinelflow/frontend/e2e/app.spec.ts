import { test, expect } from "@playwright/test";

test.describe("SentinelFlow Web Application", () => {
  test("login page renders correctly with test accounts", async ({ page }) => {
    await page.goto("/login");

    await expect(page.locator("h1")).toContainText("Sign in");
    await expect(page.getByText("Test access")).toBeVisible();
    await expect(page.locator("input[name='username']")).toBeVisible();
    await expect(page.locator("input[name='password']")).toBeVisible();
    await expect(page.locator("button[type='submit']")).toBeVisible();
  });

  test("unauthenticated access to audit page redirects to login", async ({ page }) => {
    await page.goto("/audit");
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated access to dispute page redirects to login", async ({ page }) => {
    await page.goto("/disputes/dsp_001");
    await expect(page).toHaveURL(/\/login/);
  });

  test("@visual login page visual appearance snapshot", async ({ page }) => {
    await page.goto("/login");
    // Ensure form is stable before capturing screenshot
    await page.waitForSelector("form");
    await expect(page).toHaveScreenshot("login-page.png", {
      maxDiffPixelRatio: 0.1,
    });
  });
});
