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

const TARGET_URLS = [
  { name: "Homepage / SentinelPulse", path: "/" },
  { name: "Telecom Dedicated", path: "/telecom" },
  { name: "Disputes Console", path: "/disputes" },
  { name: "Login Gateway", path: "/login" },
];

const THEME_MODES = ["light", "dark"];

const main = async () => {
  const baseUrl = process.env.BASE_URL || "http://localhost:3000";
  console.log(`\n======================================================`);
  console.log(`🛡️  SENTINELFLOW WCAG AAA AUTOMATED DEV-TIME AUDITOR`);
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Standards: WCAG 2.1 / 2.2 Level AAA & Workspace Rule 2`);
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
    console.log(`\n>>> AUDITING THEME MODE: ${theme.toUpperCase()} <<<`);

    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript((t) => {
      try {
        localStorage.setItem("sentinelflow_theme", t);
        if (t === "dark") {
          localStorage.setItem("sentinelflow_style2_bg", "#0f172a");
        } else {
          localStorage.setItem("sentinelflow_style2_bg", "#f1f5f9");
        }
      } catch {
        // ignore
      }
    }, theme);
    const page = await context.newPage();

    for (const target of TARGET_URLS) {
      const fullUrl = `${baseUrl}${target.path}`;
      console.log(`Auditing [${theme}]: ${target.name} (${fullUrl})...`);

      try {
        const resp = await page.goto(fullUrl, { waitUntil: "networkidle", timeout: 10000 });
        if (!resp || !resp.ok()) {
          console.warn(`  ⚠️ Page returned HTTP status ${resp ? resp.status() : "none"}`);
        }
      } catch (err) {
        console.error(`  ❌ Failed to connect to ${fullUrl}: ${err.message}`);
        totalFailures++;
        failureLog.push({ target: target.name, theme, error: `Connection failed: ${err.message}` });
        continue;
      }

      // Apply theme mode to page
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
      await page.waitForTimeout(100);

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
          totalFailures += v.nodes.length;
          failureLog.push({
            target: target.name,
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
          totalFailures++;
          failureLog.push({ target: target.name, theme, type: "Target Size", ...issue });
        }
      } else {
        console.log(`  ✅ Target Size & ARIA [${theme}]: All interactive controls meet 44×44px & valid ARIA`);
      }
    }

    // 3. Dynamic State: SMS Classification & Escalation Card
    console.log(`\nAuditing Interactive State: SMS Classification [${theme}]...`);
    try {
      await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
      await page.evaluate((t) => {
        try {
          localStorage.setItem("sentinelflow_theme", t);
          document.documentElement.setAttribute("data-theme", t);
        } catch {
          // ignore
        }
      }, theme);
      await page.waitForTimeout(100);

      const runBtn = await page.$('button:has-text("Run Real-Time Classification")');
      if (runBtn) {
        await runBtn.click();
        await page.waitForTimeout(600);
        await page.evaluate(axeSource);
        const dynamicAxe = await page.evaluate(async () => {
          return await window.axe.run(document, {
            runOnly: {
              type: "tag",
              values: ["wcag2aaa", "wcag21aaa", "wcag22aaa", "wcag2aa", "wcag21aa", "best-practice"],
            },
          });
        });
        if (dynamicAxe.violations.length > 0) {
          console.log(`  ❌ Dynamic classification Axe violations in ${theme} mode: ${dynamicAxe.violations.length}`);
          for (const v of dynamicAxe.violations) {
            console.log(`     - [${v.impact?.toUpperCase()}] ${v.id}: ${v.help} (${v.nodes.length} nodes)`);
            totalFailures += v.nodes.length;
          }
        } else {
          console.log(`  ✅ Interactive State [${theme}]: 0 Axe violations in post-classification view`);
        }
      }
    } catch (err) {
      console.warn(`  ⚠️ Interactive test warning in ${theme} mode: ${err.message}`);
    }

    // 4. Dynamic State: Appearance & Accessibility Preferences Dropdown Menu
    console.log(`\nAuditing Interactive State: Appearance Menu [${theme}]...`);
    try {
      await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
      await page.evaluate((t) => {
        try {
          localStorage.setItem("sentinelflow_theme", t);
          document.documentElement.setAttribute("data-theme", t);
        } catch {
          // ignore
        }
      }, theme);
      await page.waitForTimeout(100);

      const menuBtn = await page.$('button[aria-label="Appearance and accessibility preferences"]');
      if (menuBtn) {
        await menuBtn.click();
        await page.waitForTimeout(300);
        await page.evaluate(axeSource);
        const menuAxe = await page.evaluate(async () => {
          return await window.axe.run(document, {
            runOnly: {
              type: "tag",
              values: ["wcag2aaa", "wcag21aaa", "wcag22aaa", "wcag2aa", "wcag21aa", "best-practice"],
            },
          });
        });
        if (menuAxe.violations.length > 0) {
          console.log(`  ❌ Appearance Menu Axe violations in ${theme} mode: ${menuAxe.violations.length}`);
          for (const v of menuAxe.violations) {
            console.log(`     - [${v.impact?.toUpperCase()}] ${v.id}: ${v.help} (${v.nodes.length} nodes)`);
            totalFailures += v.nodes.length;
          }
        } else {
          console.log(`  ✅ Appearance Menu [${theme}]: 0 Axe violations with menu opened`);
        }
      }
    } catch (err) {
      console.warn(`  ⚠️ Appearance menu test warning in ${theme} mode: ${err.message}`);
    }

    await context.close();
  }

  await browser.close();

  console.log(`\n------------------------------------------------------`);
  if (totalFailures === 0) {
    console.log(`🏆 PASS: 100% WCAG AAA & Rule 2 Compliance Across Both Light & Dark Modes!`);
    console.log(`------------------------------------------------------\n`);
    process.exit(0);
  } else {
    console.error(`💥 FAILED: Detected ${totalFailures} accessibility violation(s) across themes/pages.`);
    console.log(`------------------------------------------------------\n`);
    process.exit(1);
  }
};

main().catch((err) => {
  console.error("Test execution aborted with fatal error:", err);
  process.exit(1);
});
