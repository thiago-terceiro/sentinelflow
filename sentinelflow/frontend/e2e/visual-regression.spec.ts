import { test, expect } from "@playwright/test";

test.describe("SentinelFlow Deterministic Visual, Layout & UX Regression Suite", () => {
  test("desktop navbar renders on a single horizontal row while mobile navbar stacks cleanly on two rows", async ({
    page,
  }) => {
    // 1. Desktop (1440x900): Brand, NavLinks, and Actions sit on one horizontal row
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.locator(".app-header-inner")).toBeVisible();

    const desktopGeometry = await page.evaluate(() => {
      const header = document.querySelector(".app-header-inner")!;
      const brand = document.querySelector(".app-brand-link")!;
      const nav = document.querySelector(".app-header-bottom")!;
      const actions = document.querySelector(".app-header-actions")!;
      return {
        headerHeight: header.getBoundingClientRect().height,
        brandMidY:
          (brand.getBoundingClientRect().top + brand.getBoundingClientRect().bottom) / 2,
        navMidY: (nav.getBoundingClientRect().top + nav.getBoundingClientRect().bottom) / 2,
        actionsMidY:
          (actions.getBoundingClientRect().top + actions.getBoundingClientRect().bottom) / 2,
      };
    });

    expect(desktopGeometry.headerHeight).toBeLessThanOrEqual(84);
    expect(Math.abs(desktopGeometry.brandMidY - desktopGeometry.navMidY)).toBeLessThanOrEqual(16);
    expect(Math.abs(desktopGeometry.brandMidY - desktopGeometry.actionsMidY)).toBeLessThanOrEqual(
      16
    );

    // 2. Mobile (375x812): Line 1 = Brand + Actions, Line 2 = NavLinks side-by-side without parentheses
    await page.setViewportSize({ width: 375, height: 812 });
    const mobileGeometry = await page.evaluate(() => {
      const brand = document.querySelector(".app-brand-link")!;
      const nav = document.querySelector(".app-header-bottom")!;
      const actions = document.querySelector(".app-header-actions")!;
      const links = Array.from(nav.querySelectorAll(".app-nav-link")).map((el) =>
        (el.textContent || "").trim()
      );
      return {
        brandBottom: brand.getBoundingClientRect().bottom,
        navTop: nav.getBoundingClientRect().top,
        brandMidY:
          (brand.getBoundingClientRect().top + brand.getBoundingClientRect().bottom) / 2,
        actionsMidY:
          (actions.getBoundingClientRect().top + actions.getBoundingClientRect().bottom) / 2,
        links,
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
      };
    });

    expect(mobileGeometry.overflowX).toBeLessThanOrEqual(1);
    expect(Math.abs(mobileGeometry.brandMidY - mobileGeometry.actionsMidY)).toBeLessThanOrEqual(18);
    expect(mobileGeometry.navTop).toBeGreaterThanOrEqual(mobileGeometry.brandBottom - 4);
    for (const label of mobileGeometry.links) {
      expect(label).not.toContain("(");
      expect(label).not.toContain(")");
    }
  });

  test("mobile appearance menu popover stays 100% inside viewport and toggles light/dark theme", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");

    const toggleBtn = page.locator(
      'button[aria-label="Appearance and accessibility preferences"]'
    );
    await expect(toggleBtn).toBeVisible();
    await toggleBtn.click();

    const dialog = page.locator("#accessibility-appearance-menu");
    await expect(dialog).toBeVisible();

    const rect = await dialog.boundingBox();
    expect(rect).not.toBeNull();
    expect(rect!.x).toBeGreaterThanOrEqual(0);
    expect(rect!.y).toBeGreaterThanOrEqual(0);
    expect(rect!.x + rect!.width).toBeLessThanOrEqual(375);
    expect(rect!.y + rect!.height).toBeLessThanOrEqual(812);

    const themeSelect = dialog.locator("#theme-select");
    await expect(themeSelect).toBeVisible();
    await themeSelect.selectOption("dark");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await themeSelect.selectOption("light");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("hero banner visual hierarchy and inline icon alignment hold on SentinelPulse and SentinelFlow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.context().addCookies([
      { name: "sentinelflow_access_token", value: "dev-reviewer", domain: "localhost", path: "/" },
      { name: "sentinelflow_test_user", value: "reviewer:reviewer", domain: "localhost", path: "/" },
    ]);

    for (const route of ["/", "/disputes"]) {
      await page.goto(route);
      await expect(page.locator('main .shell-card h1 [data-testid="hero-title-icon"]').first()).toBeVisible();

      const layout = await page.evaluate(() => {
        const heroCard = document.querySelector("main .shell-card")!;
        const h1 = heroCard.querySelector("h1")!;
        const icon = h1.querySelector('[data-testid="hero-title-icon"]')!;
        const spans = Array.from(heroCard.querySelectorAll("span"));
        const stageBadge = spans.find((s) => (s.textContent || "").trim().match(/^Stage [12]:/i))!;
        const statusSpan = spans.find((s) => (s.textContent || "").trim().match(/ACTIVE$/i))!;
        return {
          stageTop: stageBadge.getBoundingClientRect().top,
          statusTop: statusSpan.getBoundingClientRect().top,
          h1Top: h1.getBoundingClientRect().top,
          badgeRadius: parseFloat(window.getComputedStyle(stageBadge).borderTopLeftRadius || "0"),
          iconDisplay: window.getComputedStyle(icon).display,
        };
      });

      expect(layout.stageTop).toBeLessThan(layout.statusTop);
      expect(layout.statusTop).toBeLessThan(layout.h1Top);
      expect(layout.badgeRadius).toBeLessThanOrEqual(10);
      expect(layout.iconDisplay).toContain("inline");
    }
  });

  test("escalation button shows (Sign In) when unauthenticated and Contextual 'To Disputes' breadcrumb when arriving from SentinelPulse", async ({
    page,
  }) => {
    await page.route("**/app-api/telecom/classify**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "tel_esc_1",
          sender: "+14155552671",
          recipient: "+14155559876",
          message: "URGENT: Your bank account has been locked.",
          carrier: "Verizon Wireless",
          verdict: "BLOCK",
          fraud_score: 0.98,
          latency_ms: 1.9,
          timestamp: "2026-09-03T00:00:00Z",
          signals: ["IRSF_HIGH_COST_PREFIX_BURST"],
          velocity: {
            count_10s: 15,
            count_60s: 50,
            count_1h: 210,
          },
        }),
      });
    });

    // 1. Unauthenticated: button displays "Escalate to SentinelFlow (Sign In)"
    await page.goto("/telecom");
    await page.getByRole("button", { name: /Run Real-Time Classification/i }).click();

    const unauthEscalateBtn = page.getByRole("button", {
      name: /Escalate to SentinelFlow \(Sign In\)/i,
    });
    await expect(unauthEscalateBtn).toBeVisible();
    await expect(unauthEscalateBtn).toContainText("Escalate to SentinelFlow (Sign In)");

    // 2. Authenticated Reviewer arriving from SentinelPulse (?from=pulse) sees "← To Disputes"
    await page.context().addCookies([
      { name: "sentinelflow_access_token", value: "dev-reviewer", domain: "localhost", path: "/" },
      { name: "sentinelflow_test_user", value: "reviewer:reviewer", domain: "localhost", path: "/" },
    ]);

    await page.goto("/disputes/5683eeae-b598-40c7-8d0f-a222dd137065?from=pulse");
    await expect(page.getByRole("link", { name: /To Disputes/i })).toContainText("← To Disputes");

    // 3. Arriving from the Disputes Queue (no ?from=pulse) shows "← Back to disputes"
    await page.goto("/disputes/5683eeae-b598-40c7-8d0f-a222dd137065");
    await expect(page.getByRole("link", { name: /Back to disputes/i })).toContainText(
      "← Back to disputes"
    );
  });

  test("disputes queue caches list across page navigations and invalidates on manual Refresh", async ({
    page,
  }) => {
    await page.context().addCookies([
      { name: "sentinelflow_access_token", value: "dev-reviewer", domain: "localhost", path: "/" },
      { name: "sentinelflow_test_user", value: "reviewer:reviewer", domain: "localhost", path: "/" },
    ]);

    let disputesApiFetchCount = 0;
    await page.route("**/app-api/disputes", async (route) => {
      disputesApiFetchCount += 1;
      await route.continue();
    });

    // Initial visit populates cache
    const initialFetchPromise = page.waitForResponse("**/app-api/disputes");
    await page.goto("/disputes");
    await initialFetchPromise;
    await expect(page.locator("h1")).toContainText("SentinelFlow");
    const refreshBtn = page.getByRole("button", { name: /Refresh disputes list/i });
    await expect(refreshBtn).toBeVisible();

    // Navigate away via client-side navbar link and return to /disputes
    await page.locator(".app-nav-link", { hasText: "SentinelPulse" }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.locator(".app-nav-link", { hasText: "SentinelFlow" }).click();
    await expect(page).toHaveURL(/\/disputes$/);

    // Returning via client-side navigation uses the warm cache without triggering a new fetch
    expect(disputesApiFetchCount).toBe(1);

    // Clicking Refresh explicitly invalidates the cache and triggers a fresh network fetch
    await refreshBtn.click();
    await expect.poll(() => disputesApiFetchCount).toBeGreaterThan(1);
  });
});
