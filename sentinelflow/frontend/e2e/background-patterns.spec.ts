import { test, expect } from "@playwright/test";

test.describe("SentinelFlow Background Patterns & Performance", () => {
  test("wave dots canvas is mounted with GPU compositor layer", async ({ page }) => {
    await page.goto("/telecom");

    const canvas = page.locator("[data-testid='sentinel-wave-canvas']");
    await expect(canvas).toBeAttached();

    // Verify GPU compositor styling and fixed positioning
    const zIndex = await canvas.evaluate((el) => window.getComputedStyle(el).zIndex);
    const pointerEvents = await canvas.evaluate((el) => window.getComputedStyle(el).pointerEvents);
    const position = await canvas.evaluate((el) => window.getComputedStyle(el).position);

    expect(zIndex).toBe("-1");
    expect(pointerEvents).toBe("none");
    expect(position).toBe("fixed");
  });

  test("pattern selector switches modes and updates document attributes", async ({ page }) => {
    await page.goto("/telecom");

    const patternSelect = page.locator("#pattern-select");
    await expect(patternSelect).toBeVisible();

    // Verify initial default is wave-drift
    await expect(page.locator("html")).toHaveAttribute("data-pattern", "wave-drift");

    // Select plain/none
    await patternSelect.selectOption("none");
    await expect(page.locator("html")).toHaveAttribute("data-pattern", "none");

    // Verify canvas is hidden when plain/none is active
    const canvas = page.locator("[data-testid='sentinel-wave-canvas']");
    await expect(canvas).toHaveCSS("display", "none");

    // Select wave-drift again
    await patternSelect.selectOption("wave-drift");
    await expect(page.locator("html")).toHaveAttribute("data-pattern", "wave-drift");
    await expect(canvas).toHaveCSS("display", "block");
  });

  test("@visual background canvas visual appearance snapshot", async ({ page }) => {
    await page.goto("/telecom");

    const canvas = page.locator("[data-testid='sentinel-wave-canvas']");
    await expect(canvas).toBeVisible();

    // Take visual snapshot of canvas area
    await expect(canvas).toHaveScreenshot("wave-dots-canvas.png", {
      maxDiffPixelRatio: 0.15,
      animations: "disabled",
    });
  });
});
