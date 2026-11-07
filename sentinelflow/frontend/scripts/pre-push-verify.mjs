#!/usr/bin/env node
/**
 * SentinelFlow Pre-Push Deterministic Quality & Visual/A11y Gate
 *
 * Ensures that before any push:
 * 1. Code style & architecture rules pass (`npm run check:rules`)
 * 2. Strict TypeScript check passes (`tsc --noEmit`)
 * 3. Frontend unit & contract tests pass (`npm test`)
 * 4. If http://localhost:3000 is running, executes the Multi-Viewport & Multi-Theme
 *    Visual, Layout & WCAG AAA Auditor (`node scripts/test-a11y-aaa.mjs`) AND
 *    Playwright E2E + Visual Regression Suite (`npx playwright test`).
 */

import { execSync } from "node:child_process";

const runStep = (label, cmd) => {
  console.log(`\n▶ [Pre-Push Gate] ${label}...`);
  execSync(cmd, { stdio: "inherit" });
};

const isServerReachable = async (url) => {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(2500) });
    return res.ok || res.status < 500;
  } catch {
    return false;
  }
};

const main = async () => {
  console.log("======================================================");
  console.log("🛡️  SENTINELFLOW PRE-PUSH VERIFICATION GATE");
  console.log("======================================================");

  runStep("Checking Code Style & Architecture Rules", "node scripts/check-rules.js");
  runStep("Running Strict TypeScript Compiler Check", "npx tsc --noEmit");
  runStep("Running Unit & State Derivation Tests", "npm test");

  const baseUrl = process.env.A11Y_BASE_URL || "http://localhost:3000";
  const serverUp = await isServerReachable(baseUrl);

  if (serverUp) {
    runStep(
      "Running Multi-Viewport (Desktop + Mobile) & Multi-Theme (Light + Dark) Visual, Layout & WCAG AAA Auditor",
      "node scripts/test-a11y-aaa.mjs"
    );
    runStep(
      "Running Playwright E2E & Visual Regression Suite",
      "npx playwright test"
    );
  } else {
    console.warn(
      `\n⚠️  [Pre-Push Gate] Local dev server at ${baseUrl} is not currently running; skipping live browser audit in hook (CI will enforce full browser suite).`
    );
  }

  console.log("\n✅ All SentinelFlow Pre-Push Quality Gates Passed!\n");
};

main().catch((err) => {
  console.error("\n💥 Pre-Push Verification Gate FAILED. Fix all errors before pushing.");
  process.exit(1);
});
