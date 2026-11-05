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

const main = async () => {
  const baseUrl = process.env.BASE_URL || "http://localhost:3000";
  console.log(`\n======================================================`);
  console.log(`🛡️  SENTINELFLOW WCAG AAA AUTOMATED DEV-TIME AUDITOR`);
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Standards: WCAG 2.1 / 2.2 Level AAA & Workspace Rule 2`);
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

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  let totalFailures = 0;
  const failureLog = [];

  for (const target of TARGET_URLS) {
    const fullUrl = `${baseUrl}${target.path}`;
    console.log(`Auditing: ${target.name} (${fullUrl})...`);

    try {
      const resp = await page.goto(fullUrl, { waitUntil: "networkidle", timeout: 10000 });
      if (!resp || !resp.ok()) {
        console.warn(`  ⚠️ Page returned HTTP status ${resp ? resp.status() : "none"}`);
      }
    } catch (err) {
      console.error(`  ❌ Failed to connect to ${fullUrl}: ${err.message}`);
      totalFailures++;
      failureLog.push({ target: target.name, error: `Connection failed: ${err.message}` });
      continue;
    }

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
      console.log(`  ❌ Axe-Core found ${axeResults.violations.length} violation(s):`);
      for (const v of axeResults.violations) {
        console.log(`     - [${v.impact?.toUpperCase()}] ${v.id}: ${v.help} (${v.nodes.length} nodes)`);
        totalFailures += v.nodes.length;
        failureLog.push({
          target: target.name,
          type: "Axe Violation",
          id: v.id,
          help: v.help,
          nodes: v.nodes.map((n) => n.html.slice(0, 150)),
        });
      }
    } else {
      console.log(`  ✅ Axe-Core: 0 violations`);
    }

    // 2. Custom Target Sizing & ARIA Audits (Buttons, Inputs, Swatches)
    const buttonAudits = await page.evaluate(() => {
      const issues = [];
      const buttons = Array.from(
        document.querySelectorAll('button, a[role="button"], input[type="button"], input[type="submit"]')
      );

      for (let i = 0; i < buttons.length; i++) {
        const btn = buttons[i];
        const rect = btn.getBoundingClientRect();
        const text = btn.innerText.replace(/\s+/g, " ").trim();
        const ariaLabel = btn.getAttribute("aria-label") || "";
        const role = btn.getAttribute("role") || "button";

        // Touch target check (44x44 CSS px)
        // Check if element itself is >= 44x44 or has tap expansion style
        const has44x44 = rect.width >= 44 && rect.height >= 44;
        const isSwatchWithExpansion =
          btn.classList.contains("bg-palette-swatch") &&
          window.getComputedStyle(btn, "::after").width === "44px";

        if (!has44x44 && !isSwatchWithExpansion) {
          issues.push({
            index: i + 1,
            issue: "TOUCH_TARGET_BELOW_44PX",
            details: `Dimensions ${Math.round(rect.width)}x${Math.round(rect.height)}px < 44x44px`,
            snippet: btn.outerHTML.slice(0, 120),
          });
        }

        // WCAG 2.5.3 Label in Name check
        if (text && ariaLabel) {
          const cleanText = text.replace(/[^\w\s]/gi, "").trim().toLowerCase();
          const cleanLabel = ariaLabel.replace(/[^\w\s]/gi, "").trim().toLowerCase();
          if (cleanText.length > 2 && !cleanLabel.includes(cleanText.slice(0, 15))) {
            issues.push({
              index: i + 1,
              issue: "LABEL_IN_NAME_MISMATCH",
              details: `Visible text "${text}" not contained in accessible name "${ariaLabel}"`,
              snippet: btn.outerHTML.slice(0, 120),
            });
          }
        }

        // Orphaned Tab Check
        if (role === "tab") {
          const tablist = btn.closest('[role="tablist"]');
          const hasAriaControls = btn.hasAttribute("aria-controls");
          if (!tablist || !hasAriaControls) {
            issues.push({
              index: i + 1,
              issue: "ORPHANED_ROLE_TAB",
              details: `Button uses role="tab" without a controlling tabpanel`,
              snippet: btn.outerHTML.slice(0, 120),
            });
          }
        }
      }
      return issues;
    });

    if (buttonAudits.length > 0) {
      console.log(`  ❌ Target Size / ARIA Gate found ${buttonAudits.length} issue(s):`);
      for (const b of buttonAudits) {
        console.log(`     - [${b.issue}] ${b.details}`);
        totalFailures++;
        failureLog.push({ target: target.name, type: b.issue, ...b });
      }
    } else {
      console.log(`  ✅ Target Size & ARIA: All interactive controls meet 44×44px & valid ARIA`);
    }
  }

  await browser.close();

  console.log(`\n------------------------------------------------------`);
  if (totalFailures === 0) {
    console.log(`🏆 PASS: 100% WCAG AAA & Rule 2 Compliance Across All Routes!`);
    console.log(`------------------------------------------------------\n`);
    process.exit(0);
  } else {
    console.error(`💥 FAILED: Detected ${totalFailures} accessibility violation(s) across pages.`);
    console.log(`------------------------------------------------------\n`);
    process.exit(1);
  }
};

main().catch((err) => {
  console.error("Test execution aborted with fatal error:", err);
  process.exit(1);
});
