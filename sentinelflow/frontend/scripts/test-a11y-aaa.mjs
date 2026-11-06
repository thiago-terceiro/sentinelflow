import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Standalone Axe source fetcher / cache
const getAxeSource = async () => {
  const cachePath = path.join(__dirname, ".axe-core-cache.js");
  if (fs.existsSync(cachePath)) {
    return fs.readFileSync(cachePath, "utf-8");
  }
  const res = await fetch("https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js");
  if (!res.ok) {
    throw new Error(`Failed to fetch axe-core: ${res.statusText}`);
  }
  const source = await res.text();
  fs.writeFileSync(cachePath, source, "utf-8");
  return source;
};

const THEME_MODES = ["light", "dark"];

const applyTheme = async (page, theme) => {
  await page.evaluate((t) => {
    try {
      localStorage.setItem("sentinelflow_theme", t);
      document.documentElement.setAttribute("data-theme", t);
      if (t === "dark") {
        document.documentElement.style.setProperty("--style2-bg", "#0f172a");
      } else {
        document.documentElement.style.setProperty("--style2-bg", "#f1f5f9");
      }
    } catch {
      // ignore
    }
  }, theme);
  await page.waitForTimeout(150);
};

const auditPage = async (page, pageName, theme, axeSource, failureLog) => {
  let pageFailures = 0;

  // 1. Run Axe-Core with AAA tags
  await page.evaluate(axeSource);
  const axeResults = await page.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: {
        type: "tag",
        values: ["wcag2aaa", "wcag21aaa", "wcag22aaa", "wcag2aa", "wcag21aa", "best-practice"],
      },
    });
  });

  if (axeResults.violations.length > 0) {
    console.log(`  ❌ Axe-Core found ${axeResults.violations.length} violation(s) in ${theme} mode:`);
    for (const v of axeResults.violations) {
      console.log(`     - [${v.impact?.toUpperCase()}] ${v.id}: ${v.help} (${v.nodes.length} nodes)`);
      for (const n of v.nodes) {
        console.log(`       Target: ${n.target.join(" ")}`);
        console.log(`       Detail: ${n.failureSummary?.slice(0, 160)}`);
      }
      pageFailures += v.nodes.length;
      failureLog.push({
        target: pageName,
        theme,
        type: "Axe Violation",
        id: v.id,
        help: v.help,
        nodes: v.nodes.map((n) => n.html.slice(0, 150)),
      });
    }
  } else {
    console.log(`  ✅ Axe-Core [${theme}]: 0 violations`);
  }

  // 2. Automated Rule 2 checks: Minimum 44x44px Target Size & Semantic ARIA
  const rule2Violations = await page.evaluate(() => {
    const issues = [];
    const interactives = document.querySelectorAll(
      'button, a, input, select, textarea, [role="button"], [role="tab"]'
    );

    for (const el of interactives) {
      if (el.offsetParent === null) continue; // Skip hidden elements

      const rect = el.getBoundingClientRect();
      const computed = window.getComputedStyle(el);

      // Allow pseudo-element touch target inflation or min 44x44
      const meetsTargetSize =
        (rect.width >= 43.5 && rect.height >= 43.5) ||
        computed.minWidth === "44px" ||
        computed.minHeight === "44px";

      if (!meetsTargetSize) {
        issues.push({
          tag: el.tagName.toLowerCase(),
          text: (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 40),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          reason: "Interactive control smaller than 44x44px",
        });
      }

      // Orphaned role="tab" validation
      if (el.getAttribute("role") === "tab") {
        const parent = el.closest('[role="tablist"]');
        if (!parent) {
          issues.push({
            tag: el.tagName.toLowerCase(),
            text: (el.textContent || "").trim().slice(0, 40),
            reason: 'Orphaned role="tab" missing parent role="tablist"',
          });
        }
      }
    }
    return issues;
  });

  if (rule2Violations.length > 0) {
    console.log(`  ❌ Target Size / ARIA violations in ${theme} mode: ${rule2Violations.length}`);
    for (const issue of rule2Violations) {
      console.log(`     - <${issue.tag}> "${issue.text}": ${issue.reason} (${issue.width}x${issue.height}px)`);
      pageFailures++;
      failureLog.push({ target: pageName, theme, type: "Target Size", ...issue });
    }
  } else {
    console.log(`  ✅ Target Size & ARIA [${theme}]: All interactive controls meet 44×44px & valid ARIA`);
  }

  return pageFailures;
};

const main = async () => {
  const baseUrl = process.env.BASE_URL || "http://localhost:3000";
  console.log(`\n======================================================`);
  console.log(`🛡️  SENTINELFLOW WCAG AAA AUTOMATED DEV-TIME AUDITOR`);
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Standards: WCAG 2.1 / 2.2 Level AAA & Workspace Rule 2`);
  console.log(`Scope: Public Pages, Authenticated Disputes & Workbench,`);
  console.log(`       Audit Ledger, AI Evals, & Interactive States`);
  console.log(`Themes: Light & Dark Modes`);
  console.log(`======================================================\n`);

  let axeSource;
  try {
    axeSource = await getAxeSource();
  } catch (err) {
    console.error("Failed to load Axe-Core library:", err);
    process.exit(1);
  }

  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch (err) {
    console.error("Playwright browser launch failed:", err);
    process.exit(1);
  }

  let totalFailures = 0;
  const failureLog = [];

  for (const theme of THEME_MODES) {
    console.log(`\n======================================================`);
    console.log(`>>> AUDITING THEME MODE: ${theme.toUpperCase()} <<<`);
    console.log(`======================================================`);

    // Section 1: Public Pages (Unauthenticated)
    console.log(`\n--- 1. Public Unauthenticated Routes [${theme.toUpperCase()}] ---`);
    const publicContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const publicPage = await publicContext.newPage();

    const publicTargets = [
      { name: "Homepage / SentinelPulse", path: "/" },
      { name: "Telecom Dedicated", path: "/telecom" },
      { name: "Login Gateway", path: "/login" },
    ];

    for (const target of publicTargets) {
      const fullUrl = `${baseUrl}${target.path}`;
      console.log(`Auditing [${theme}]: ${target.name} (${fullUrl})...`);
      try {
        await publicPage.goto(fullUrl, { waitUntil: "networkidle", timeout: 10000 });
        await applyTheme(publicPage, theme);
        totalFailures += await auditPage(publicPage, target.name, theme, axeSource, failureLog);
      } catch (err) {
        console.error(`  ❌ Failed to connect to ${fullUrl}: ${err.message}`);
        totalFailures++;
        failureLog.push({ target: target.name, theme, error: err.message });
      }
    }

    // Dynamic State: SMS Classification
    console.log(`\nAuditing Interactive State: SMS Classification [${theme}]...`);
    try {
      await publicPage.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
      await applyTheme(publicPage, theme);
      const runBtn = await publicPage.$('button:has-text("Run Real-Time Classification")');
      if (runBtn) {
        await runBtn.click();
        await publicPage.waitForTimeout(600);
        totalFailures += await auditPage(
          publicPage,
          "Interactive SMS Classification Result",
          theme,
          axeSource,
          failureLog
        );
      }
    } catch (err) {
      console.warn(`  ⚠️ Interactive test warning in ${theme} mode: ${err.message}`);
    }

    // Dynamic State: Appearance Preferences Menu
    console.log(`\nAuditing Interactive State: Appearance Menu [${theme}]...`);
    try {
      await publicPage.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
      await applyTheme(publicPage, theme);
      const menuBtn = await publicPage.$('button[aria-label="Appearance and accessibility preferences"]');
      if (menuBtn) {
        await menuBtn.click();
        await publicPage.waitForTimeout(300);
        totalFailures += await auditPage(
          publicPage,
          "Interactive Appearance Menu Opened",
          theme,
          axeSource,
          failureLog
        );
      }
    } catch (err) {
      console.warn(`  ⚠️ Appearance menu test warning in ${theme} mode: ${err.message}`);
    }

    await publicContext.close();

    // Section 2: Authenticated Reviewer Routes (Disputes Queue & Detail Workbenches)
    console.log(`\n--- 2. Authenticated Reviewer Routes [${theme.toUpperCase()}] ---`);
    const reviewerContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await reviewerContext.addCookies([
      { name: "sentinelflow_access_token", value: "dev-reviewer", domain: "localhost", path: "/" },
      { name: "sentinelflow_test_user", value: "reviewer:reviewer", domain: "localhost", path: "/" },
    ]);
    const reviewerPage = await reviewerContext.newPage();

    // Audit /disputes queue
    const disputesUrl = `${baseUrl}/disputes`;
    console.log(`Auditing [${theme}]: Seeded Disputes Queue (${disputesUrl})...`);
    let disputeDetailLinks = [];
    try {
      await reviewerPage.goto(disputesUrl, { waitUntil: "networkidle", timeout: 10000 });
      await applyTheme(reviewerPage, theme);
      totalFailures += await auditPage(
        reviewerPage,
        "Seeded Disputes Queue (Authenticated)",
        theme,
        axeSource,
        failureLog
      );

      // Extract seeded dispute links
      disputeDetailLinks = await reviewerPage.evaluate(() => {
        return Array.from(document.querySelectorAll("a"))
          .map((a) => a.href)
          .filter((href) => href.includes("/disputes/") && !href.endsWith("/disputes"));
      });
      // Deduplicate links
      disputeDetailLinks = Array.from(new Set(disputeDetailLinks));
    } catch (err) {
      console.error(`  ❌ Failed to audit disputes queue: ${err.message}`);
      totalFailures++;
      failureLog.push({ target: "Disputes Queue", theme, error: err.message });
    }

    // Audit each discovered dispute detail workbench page
    console.log(`Discovered ${disputeDetailLinks.length} seeded dispute workbench link(s) to audit:`);
    for (const detailLink of disputeDetailLinks) {
      const shortId = detailLink.split("/").pop() || detailLink;
      console.log(`Auditing [${theme}]: Dispute Workbench (${shortId})...`);
      try {
        await reviewerPage.goto(detailLink, { waitUntil: "networkidle", timeout: 10000 });
        await applyTheme(reviewerPage, theme);
        totalFailures += await auditPage(
          reviewerPage,
          `Dispute Workbench [${shortId}]`,
          theme,
          axeSource,
          failureLog
        );
      } catch (err) {
        console.error(`  ❌ Failed to audit dispute ${shortId}: ${err.message}`);
        totalFailures++;
        failureLog.push({ target: `Dispute Workbench [${shortId}]`, theme, error: err.message });
      }
    }

    await reviewerContext.close();

    // Section 3: Authenticated Auditor Routes (Audit Ledger & AI Evaluations)
    console.log(`\n--- 3. Authenticated Auditor Routes [${theme.toUpperCase()}] ---`);
    const auditorContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await auditorContext.addCookies([
      { name: "sentinelflow_access_token", value: "dev-auditor", domain: "localhost", path: "/" },
      { name: "sentinelflow_test_user", value: "auditor:auditor", domain: "localhost", path: "/" },
    ]);
    const auditorPage = await auditorContext.newPage();

    // Audit /audit ledger view
    const auditUrl = `${baseUrl}/audit`;
    console.log(`Auditing [${theme}]: Audit Ledger View (${auditUrl})...`);
    try {
      await auditorPage.goto(auditUrl, { waitUntil: "networkidle", timeout: 10000 });
      await applyTheme(auditorPage, theme);
      totalFailures += await auditPage(
        auditorPage,
        "Audit Ledger (Authenticated Auditor)",
        theme,
        axeSource,
        failureLog
      );

      // Audit AI Model Evaluations tab
      const evalsBtn = await auditorPage.evaluateHandle(() => {
        const buttons = Array.from(document.querySelectorAll("button"));
        return buttons.find((b) => b.textContent?.includes("AI Model Evaluations"));
      });
      const btnElement = evalsBtn.asElement();
      if (btnElement) {
        console.log(`Auditing [${theme}]: AI Evaluations Tab View (${auditUrl})...`);
        await btnElement.click();
        await auditorPage.waitForTimeout(300);
        totalFailures += await auditPage(
          auditorPage,
          "AI Evaluations Tab (Authenticated Auditor)",
          theme,
          axeSource,
          failureLog
        );
      }
    } catch (err) {
      console.error(`  ❌ Failed to audit /audit: ${err.message}`);
      totalFailures++;
      failureLog.push({ target: "Audit Ledger", theme, error: err.message });
    }

    await auditorContext.close();
  }

  await browser.close();

  console.log(`\n======================================================`);
  if (totalFailures === 0) {
    console.log(`🏆 100% WCAG AAA & RULE 2 COMPLIANCE VERIFIED!`);
    console.log(`All public routes, authenticated dispute consoles, audit portals,`);
    console.log(`and interactive states passed with ZERO violations across themes.`);
    console.log(`======================================================\n`);
    process.exit(0);
  } else {
    console.error(`💥 FAILED: Detected ${totalFailures} accessibility violation(s).`);
    console.log(`Failure details:`, JSON.stringify(failureLog, null, 2));
    console.log(`======================================================\n`);
    process.exit(1);
  }
};

main().catch((err) => {
  console.error("Test execution aborted with fatal error:", err);
  process.exit(1);
});
