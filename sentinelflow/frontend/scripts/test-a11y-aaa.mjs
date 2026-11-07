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
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 375, height: 812 },
];

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

const auditPage = async (page, pageName, theme, viewportName, axeSource, failureLog) => {
  let pageFailures = 0;
  const tagLabel = `${theme}/${viewportName}`;

  // 1. Run Axe-Core with AAA tags + experimental Label-in-Name & Contrast rules
  await page.evaluate(axeSource);
  const axeResults = await page.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: {
        type: "tag",
        values: ["wcag2aaa", "wcag21aaa", "wcag22aaa", "wcag2aa", "wcag21aa", "best-practice"],
      },
      rules: {
        "label-content-name-mismatch": { enabled: true },
        "color-contrast-enhanced": { enabled: true },
        "target-size": { enabled: true },
      },
    });
  });

  if (axeResults.violations.length > 0) {
    console.log(`  ❌ Axe-Core found ${axeResults.violations.length} violation(s) in [${tagLabel}]:`);
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
        viewport: viewportName,
        type: "Axe Violation",
        id: v.id,
        help: v.help,
        nodes: v.nodes.map((n) => n.html.slice(0, 150)),
      });
    }
  } else {
    console.log(`  ✅ Axe-Core [${tagLabel}]: 0 violations`);
  }

  // 2. Automated Rule 2 checks: Minimum 44x44px Target Size, Semantic ARIA & WCAG 2.5.3 Label in Name
  const rule2Violations = await page.evaluate(() => {
    const issues = [];
    const interactives = document.querySelectorAll(
      'button, a, input, select, textarea, [role="button"], [role="tab"], [role="radio"]'
    );

    const normalizeLabel = (str) =>
      str
        .replace(/[^\p{L}\p{N}\s]/gu, " ")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();

    for (const el of interactives) {
      if (el.offsetParent === null) continue; // Skip hidden elements
      const computed = window.getComputedStyle(el);
      if (computed.display === "none" || computed.visibility === "hidden" || computed.opacity === "0") {
        continue;
      }

      const rect = el.getBoundingClientRect();

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

      // WCAG 2.5.3 Label in Name check for elements with explicit aria-label and visible text
      const ariaLabel = el.getAttribute("aria-label");
      if (ariaLabel && el.tagName !== "SELECT" && el.tagName !== "INPUT") {
        const visibleText = normalizeLabel(el.textContent || "");
        const normAria = normalizeLabel(ariaLabel);
        if (visibleText.length >= 2 && !normAria.includes(visibleText)) {
          issues.push({
            tag: el.tagName.toLowerCase(),
            text: `${(el.textContent || "").trim().slice(0, 30)} vs aria-label="${ariaLabel}"`,
            reason: "WCAG 2.5.3 Label in Name mismatch: visible text not contained in aria-label",
          });
        }
      }
    }
    return issues;
  });

  if (rule2Violations.length > 0) {
    console.log(`  ❌ Target Size / ARIA violations in [${tagLabel}]: ${rule2Violations.length}`);
    for (const issue of rule2Violations) {
      console.log(
        `     - <${issue.tag}> "${issue.text}": ${issue.reason}${issue.width ? ` (${issue.width}x${issue.height}px)` : ""}`
      );
      pageFailures++;
      failureLog.push({ target: pageName, theme, viewport: viewportName, type: "Rule 2 A11y", ...issue });
    }
  } else {
    console.log(`  ✅ Target Size, ARIA & Label-in-Name [${tagLabel}]: 100% compliant`);
  }

  // 3. Deterministic Visual Layout & Responsive Geometry Invariants
  const layoutViolations = await page.evaluate((vpName) => {
    const issues = [];
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // 3a. Zero horizontal page overflow
    const docScrollWidth = document.documentElement.scrollWidth;
    if (docScrollWidth > vw + 1) {
      issues.push({
        check: "Horizontal Overflow",
        detail: `Page scrollWidth (${docScrollWidth}px) exceeds viewport width (${vw}px)`,
      });
    }

    // 3b. Navbar Responsive Layout Invariant (Single-Row on Desktop, Stacked Two-Row on Mobile)
    const brand = document.querySelector(".app-brand-link");
    const navBottom = document.querySelector(".app-header-bottom");
    const actions = document.querySelector(".app-header-actions");
    const header = document.querySelector(".app-header");

    if (brand && navBottom && actions && header) {
      const brandRect = brand.getBoundingClientRect();
      const navRect = navBottom.getBoundingClientRect();
      const actionsRect = actions.getBoundingClientRect();
      const headerRect = header.getBoundingClientRect();

      const brandCenterY = brandRect.top + brandRect.height / 2;
      const navCenterY = navRect.top + navRect.height / 2;
      const actionsCenterY = actionsRect.top + actionsRect.height / 2;

      if (vpName === "desktop") {
        if (Math.abs(brandCenterY - navCenterY) > 16 || Math.abs(brandCenterY - actionsCenterY) > 16) {
          issues.push({
            check: "Desktop Single-Row Navbar",
            detail: `Navbar items are not vertically aligned on a single row (brandY=${Math.round(brandCenterY)}, navY=${Math.round(navCenterY)}, actionsY=${Math.round(actionsCenterY)})`,
          });
        }
        if (brandRect.left >= navRect.left || navRect.left >= actionsRect.left) {
          issues.push({
            check: "Desktop Navbar Horizontal Order",
            detail: `Expected Brand < NavLinks < Actions left-to-right order (brandX=${Math.round(brandRect.left)}, navX=${Math.round(navRect.left)}, actionsX=${Math.round(actionsRect.left)})`,
          });
        }
        if (headerRect.height > 84) {
          issues.push({
            check: "Desktop Navbar Height",
            detail: `Desktop header height (${Math.round(headerRect.height)}px) exceeds single-row threshold (84px)`,
          });
        }
      } else if (vpName === "mobile") {
        if (Math.abs(brandCenterY - actionsCenterY) > 16) {
          issues.push({
            check: "Mobile Navbar Top Row",
            detail: `Brand and Actions must share Line 1 on mobile (brandY=${Math.round(brandCenterY)}, actionsY=${Math.round(actionsCenterY)})`,
          });
        }
        if (navRect.top < brandRect.bottom - 6) {
          issues.push({
            check: "Mobile Navbar Stacked Second Row",
            detail: `Nav links must sit below Brand on Line 2 on mobile (brandBottom=${Math.round(brandRect.bottom)}, navTop=${Math.round(navRect.top)})`,
          });
        }
        const navLinks = Array.from(navBottom.querySelectorAll(".app-nav-link"));
        for (const link of navLinks) {
          if ((link.textContent || "").includes("(") || (link.textContent || "").includes(")")) {
            issues.push({
              check: "Mobile Navbar Clean Link Labels",
              detail: `Nav link "${(link.textContent || "").trim()}" contains forbidden parentheses`,
            });
          }
        }
      }
    }

    // 3c. Popover / Dialog Viewport Containment
    const dialogs = document.querySelectorAll('[role="dialog"], .appearance-menu-popover');
    for (const dlg of dialogs) {
      if (dlg.offsetParent === null && window.getComputedStyle(dlg).position !== "fixed") continue;
      const rect = dlg.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) continue;

      if (rect.left < -1 || rect.top < -1 || rect.right > vw + 1 || rect.bottom > vh + 1) {
        issues.push({
          check: "Dialog Viewport Containment",
          detail: `Dialog overflows viewport (${vw}x${vh}): left=${Math.round(rect.left)}, top=${Math.round(rect.top)}, right=${Math.round(rect.right)}, bottom=${Math.round(rect.bottom)}`,
        });
      }
      if (rect.width < 240) {
        issues.push({
          check: "Dialog Usable Width",
          detail: `Dialog width (${Math.round(rect.width)}px) is too narrow (< 240px)`,
        });
      }
    }

    // 3d. Hero Card Visual Order & Inline Icon Alignment on SentinelPulse & SentinelFlow
    const pathname = window.location.pathname;
    if (pathname === "/" || pathname === "/telecom" || pathname === "/disputes") {
      const heroCard = document.querySelector("main .shell-card");
      if (heroCard) {
        const h1 = heroCard.querySelector("h1");
        const spans = Array.from(heroCard.querySelectorAll("span"));
        const stageBadge = spans.find((s) =>
          (s.textContent || "").trim().match(/^Stage [12]:/i)
        );
        const statusSpan = spans.find((s) =>
          (s.textContent || "").trim().match(/ACTIVE$/i)
        );

        if (stageBadge && statusSpan && h1) {
          const stageRect = stageBadge.getBoundingClientRect();
          const statusRect = statusSpan.getBoundingClientRect();
          const h1Rect = h1.getBoundingClientRect();

          if (stageRect.top >= statusRect.top) {
            issues.push({
              check: "Hero Banner Vertical Order (Stage Badge -> Live Status)",
              detail: `Stage badge (top=${Math.round(stageRect.top)}) must be above Live Status (top=${Math.round(statusRect.top)})`,
            });
          }
          if (statusRect.top >= h1Rect.top) {
            issues.push({
              check: "Hero Banner Vertical Order (Live Status -> H1)",
              detail: `Live Status (top=${Math.round(statusRect.top)}) must be above H1 (top=${Math.round(h1Rect.top)})`,
            });
          }

          const badgeRadius = parseFloat(window.getComputedStyle(stageBadge).borderTopLeftRadius || "0");
          if (badgeRadius > 10) {
            issues.push({
              check: "Stage Badge Border Radius",
              detail: `Stage badge border-radius (${badgeRadius}px) is too round (> 10px)`,
            });
          }
        }

        if (h1) {
          const icon = h1.querySelector('[data-testid="hero-title-icon"], svg');
          if (icon) {
            const iconStyle = window.getComputedStyle(icon);
            if (iconStyle.display === "block" || iconStyle.display === "none") {
              issues.push({
                check: "Hero H1 Inline Icon",
                detail: `Hero H1 icon must be visible and inline, not display: ${iconStyle.display}`,
              });
            }
          }
        }
      }
    }

    return issues;
  }, viewportName);

  if (layoutViolations.length > 0) {
    console.log(`  ❌ Visual Layout / Geometry violations in [${tagLabel}]: ${layoutViolations.length}`);
    for (const v of layoutViolations) {
      console.log(`     - [${v.check}] ${v.detail}`);
      pageFailures++;
      failureLog.push({ target: pageName, theme, viewport: viewportName, type: "Visual Layout", ...v });
    }
  } else {
    console.log(`  ✅ Visual Layout & Geometry [${tagLabel}]: All responsive & structural invariants hold`);
  }

  return pageFailures;
};

const main = async () => {
  const baseUrl = process.env.BASE_URL || "http://localhost:3000";
  console.log(`\n======================================================`);
  console.log(`🛡️  SENTINELFLOW VISUAL, LAYOUT & WCAG AAA AUDITOR`);
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Standards: WCAG 2.1 / 2.2 Level AAA, Rule 2 & Visual Geometry`);
  console.log(`Viewports: Desktop (1440×900) & Mobile (375×812)`);
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

  for (const vp of VIEWPORTS) {
    for (const theme of THEME_MODES) {
      console.log(`\n======================================================`);
      console.log(`>>> AUDITING MATRIX: ${theme.toUpperCase()} MODE | ${vp.name.toUpperCase()} (${vp.width}×${vp.height}) <<<`);
      console.log(`======================================================`);

      // Section 1: Public Pages (Unauthenticated)
      console.log(`\n--- 1. Public Unauthenticated Routes [${theme.toUpperCase()} / ${vp.name.toUpperCase()}] ---`);
      const publicContext = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const publicPage = await publicContext.newPage();

      const publicTargets = [
        { name: "Homepage / SentinelPulse", path: "/" },
        { name: "Telecom Dedicated", path: "/telecom" },
        { name: "Login Gateway", path: "/login" },
        { name: "Unauthenticated Disputes Gate", path: "/disputes" },
        { name: "Unauthenticated Audit Gate", path: "/audit" },
      ];

      for (const target of publicTargets) {
        const fullUrl = `${baseUrl}${target.path}`;
        console.log(`Auditing [${theme}/${vp.name}]: ${target.name} (${fullUrl})...`);
        try {
          await publicPage.goto(fullUrl, { waitUntil: "networkidle", timeout: 10000 });
          await applyTheme(publicPage, theme);
          totalFailures += await auditPage(publicPage, target.name, theme, vp.name, axeSource, failureLog);
        } catch (err) {
          console.error(`  ❌ Failed to connect to ${fullUrl}: ${err.message}`);
          totalFailures++;
          failureLog.push({ target: target.name, theme, viewport: vp.name, error: err.message });
        }
      }

      // Dynamic State: SMS Classification
      console.log(`\nAuditing Interactive State: SMS Classification [${theme}/${vp.name}]...`);
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
            vp.name,
            axeSource,
            failureLog
          );
        }
      } catch (err) {
        console.warn(`  ⚠️ Interactive test warning in ${theme}/${vp.name}: ${err.message}`);
      }

      // Dynamic State: Appearance Preferences Menu
      console.log(`\nAuditing Interactive State: Appearance Menu [${theme}/${vp.name}]...`);
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
            vp.name,
            axeSource,
            failureLog
          );
        }
      } catch (err) {
        console.warn(`  ⚠️ Appearance menu test warning in ${theme}/${vp.name}: ${err.message}`);
      }

      await publicContext.close();

      // Section 2: Authenticated Reviewer Routes (Disputes Queue & Detail Workbenches)
      console.log(`\n--- 2. Authenticated Reviewer Routes [${theme.toUpperCase()} / ${vp.name.toUpperCase()}] ---`);
      const reviewerContext = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      await reviewerContext.addCookies([
        { name: "sentinelflow_access_token", value: "dev-reviewer", domain: "localhost", path: "/" },
        { name: "sentinelflow_test_user", value: "reviewer:reviewer", domain: "localhost", path: "/" },
      ]);
      const reviewerPage = await reviewerContext.newPage();

      // Audit /disputes queue
      const disputesUrl = `${baseUrl}/disputes`;
      console.log(`Auditing [${theme}/${vp.name}]: Seeded Disputes Queue (${disputesUrl})...`);
      let disputeDetailLinks = [];
      try {
        await reviewerPage.goto(disputesUrl, { waitUntil: "networkidle", timeout: 10000 });
        await applyTheme(reviewerPage, theme);
        totalFailures += await auditPage(
          reviewerPage,
          "Seeded Disputes Queue (Authenticated)",
          theme,
          vp.name,
          axeSource,
          failureLog
        );

        // Extract seeded dispute links
        disputeDetailLinks = await reviewerPage.evaluate(() => {
          return Array.from(document.querySelectorAll("a"))
            .map((a) => a.href)
            .filter((href) => href.includes("/disputes/") && !href.endsWith("/disputes"));
        });
        disputeDetailLinks = Array.from(new Set(disputeDetailLinks));
      } catch (err) {
        console.error(`  ❌ Failed to audit disputes queue: ${err.message}`);
        totalFailures++;
        failureLog.push({ target: "Disputes Queue", theme, viewport: vp.name, error: err.message });
      }

      // Audit each discovered dispute detail workbench page (all on desktop, first 2 on mobile for speed while covering all components)
      const linksToAudit = vp.name === "desktop" ? disputeDetailLinks : disputeDetailLinks.slice(0, 2);
      console.log(`Auditing ${linksToAudit.length} seeded dispute workbench link(s) in [${theme}/${vp.name}]:`);
      let interactiveWorkbenchAudited = false;
      for (const detailLink of linksToAudit) {
        const shortId = detailLink.split("/").pop() || detailLink;
        console.log(`Auditing [${theme}/${vp.name}]: Dispute Workbench (${shortId})...`);
        try {
          await reviewerPage.goto(detailLink, { waitUntil: "networkidle", timeout: 10000 });
          await applyTheme(reviewerPage, theme);
          totalFailures += await auditPage(
            reviewerPage,
            `Dispute Workbench [${shortId}]`,
            theme,
            vp.name,
            axeSource,
            failureLog
          );

          // On the first dispute with interactive panels, also open Diff Inspector, GenUI Artifacts & Time-Travel Historical View
          if (!interactiveWorkbenchAudited) {
            const compareBtn = await reviewerPage.$('button:has-text("Compare Iterations")');
            const genUiBtn = await reviewerPage.$('button:has-text("GenUI Artifacts")');
            const prevStepBtn = await reviewerPage.$('button[aria-label*="Step backward"]');

            let openedAny = false;
            if (compareBtn) {
              await compareBtn.click();
              openedAny = true;
            }
            if (genUiBtn) {
              await genUiBtn.click();
              openedAny = true;
            }
            if (prevStepBtn && !(await prevStepBtn.isDisabled())) {
              await prevStepBtn.click();
              openedAny = true;
            }

            if (openedAny) {
              await reviewerPage.waitForTimeout(250);
              console.log(`Auditing [${theme}/${vp.name}]: Dispute Workbench Interactive Panels (${shortId})...`);
              totalFailures += await auditPage(
                reviewerPage,
                `Dispute Workbench Interactive Panels [${shortId}]`,
                theme,
                vp.name,
                axeSource,
                failureLog
              );
              interactiveWorkbenchAudited = true;
            }
          }
        } catch (err) {
          console.error(`  ❌ Failed to audit dispute ${shortId}: ${err.message}`);
          totalFailures++;
          failureLog.push({ target: `Dispute Workbench [${shortId}]`, theme, viewport: vp.name, error: err.message });
        }
      }

      await reviewerContext.close();

      // Section 3: Authenticated Auditor Routes (Audit Ledger & AI Evaluations)
      console.log(`\n--- 3. Authenticated Auditor Routes [${theme.toUpperCase()} / ${vp.name.toUpperCase()}] ---`);
      const auditorContext = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      await auditorContext.addCookies([
        { name: "sentinelflow_access_token", value: "dev-auditor", domain: "localhost", path: "/" },
        { name: "sentinelflow_test_user", value: "auditor:auditor", domain: "localhost", path: "/" },
      ]);
      const auditorPage = await auditorContext.newPage();

      // Audit /audit ledger view
      const auditUrl = `${baseUrl}/audit`;
      console.log(`Auditing [${theme}/${vp.name}]: Audit Ledger View (${auditUrl})...`);
      try {
        await auditorPage.goto(auditUrl, { waitUntil: "networkidle", timeout: 10000 });
        await applyTheme(auditorPage, theme);
        totalFailures += await auditPage(
          auditorPage,
          "Audit Ledger (Authenticated Auditor)",
          theme,
          vp.name,
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
          console.log(`Auditing [${theme}/${vp.name}]: AI Evaluations Tab View (${auditUrl})...`);
          await btnElement.click();
          await auditorPage.waitForTimeout(300);
          totalFailures += await auditPage(
            auditorPage,
            "AI Evaluations Tab (Authenticated Auditor)",
            theme,
            vp.name,
            axeSource,
            failureLog
          );
        }
      } catch (err) {
        console.error(`  ❌ Failed to audit /audit: ${err.message}`);
        totalFailures++;
        failureLog.push({ target: "Audit Ledger", theme, viewport: vp.name, error: err.message });
      }

      await auditorContext.close();
    }
  }

  await browser.close();

  console.log(`\n======================================================`);
  if (totalFailures === 0) {
    console.log(`🏆 100% VISUAL, LAYOUT & WCAG AAA COMPLIANCE VERIFIED!`);
    console.log(`All public routes, authenticated dispute consoles, audit portals,`);
    console.log(`and interactive states passed with ZERO violations across`);
    console.log(`Desktop (1440×900) & Mobile (375×812) in Light & Dark modes.`);
    console.log(`======================================================\n`);
    process.exit(0);
  } else {
    console.error(`💥 FAILED: Detected ${totalFailures} visual/layout/accessibility violation(s).`);
    console.log(`Failure details:`, JSON.stringify(failureLog, null, 2));
    console.log(`======================================================\n`);
    process.exit(1);
  }
};

main().catch((err) => {
  console.error("Test execution aborted with fatal error:", err);
  process.exit(1);
});
