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
    await page.waitForSelector("form");
    await expect(page).toHaveScreenshot("login-page.png", {
      maxDiffPixelRatio: 0.1,
    });
  });

  test("investigation workbench supports cold-hydration, time-travel scrubbing, diffing, and sticky citation pinning", async ({
    page,
  }) => {
    await page.context().addCookies([
      {
        name: "sf_session",
        value: "e2e-mock-token",
        domain: "localhost",
        path: "/",
      },
    ]);

    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ username: "analyst", role: "analyst" }),
      });
    });

    await page.route("**/api/v1/disputes/dsp_001", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "dsp_001",
          customer_id: "cust_001",
          merchant_name: "ElectroMart",
          amount: 1450.0,
          currency: "USD",
          reason: "Unauthorized online transaction",
          status: "investigating",
          created_at: "2026-09-03T00:00:00Z",
        }),
      });
    });

    await page.route("**/api/v1/disputes/dsp_001/investigations/latest", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "inv_e2e_1",
          dispute_id: "dsp_001",
          thread_id: "thread_e2e_1",
          status: "completed",
          created_at: "2026-09-03T00:00:00Z",
          updated_at: "2026-09-03T00:00:10Z",
          budget: {
            max_iterations: 2,
            max_tool_calls: 6,
            max_analyzer_calls: 4,
            max_tokens: 12000,
            max_seconds: 45,
          },
          risk_assessment: {
            score: 0.89,
            level: "high",
            explanation: "Confirmed account takeover via proxy.",
            factors: [{ name: "velocity", weight: 0.5, value: 0.9, rationale: "High velocity" }],
          },
          compliance_findings: [],
          report: {
            conclusion: "Confirmed unauthorized charge.",
            recommendation: "approve_refund",
            confidence: 0.92,
            hypotheses: [],
            risk_factors: ["High velocity"],
            evidence_ids: ["ev_tx_1"],
            unresolved_questions: [],
            compliance_findings: [],
          },
          evidence: [
            {
              id: "ev_tx_1",
              source: "transactions",
              category: "transaction",
              origin: "observed_fact",
              summary: "High-value electronics charge from foreign IP",
              facts: { amount: 1450 },
              confidence: 0.96,
              collected_at: "2026-09-03T00:00:02Z",
              provenance: "ledger",
            },
          ],
          analyzer_summaries: [
            {
              analyzer: "fraud_pattern",
              origin: "analyzer_interpretation",
              summary: "Anomaly detected in cardholder velocity",
              findings: ["Proxy IP detected"],
              confidence: 0.9,
              evidence_ids: ["ev_tx_1"],
              contradictions: [],
              recommended_followups: [],
            },
          ],
          hypotheses: [
            {
              statement: "Automated credential stuffing via proxy",
              confidence: 0.92,
              supporting_evidence_ids: ["ev_tx_1"],
              contradicting_evidence_ids: [],
            },
          ],
          timeline_events: [
            {
              id: "evt_1",
              type: "evidence_added",
              timestamp: "2026-09-03T00:00:02Z",
              data: {
                id: "ev_tx_1",
                source: "transactions",
                category: "transaction",
                origin: "observed_fact",
                summary: "High-value electronics charge from foreign IP",
                facts: { amount: 1450 },
                confidence: 0.96,
                collected_at: "2026-09-03T00:00:02Z",
                provenance: "ledger",
              },
            },
            {
              id: "evt_2",
              type: "hypothesis_updated",
              timestamp: "2026-09-03T00:00:04Z",
              data: {
                iteration: 1,
                hypotheses: [
                  {
                    statement: "Initial friendly fraud check",
                    confidence: 0.55,
                    supporting_evidence_ids: ["ev_tx_1"],
                    contradicting_evidence_ids: [],
                  },
                ],
                unresolved_questions: ["Verify proxy ASN?"],
              },
            },
            {
              id: "evt_3",
              type: "hypothesis_updated",
              timestamp: "2026-09-03T00:00:08Z",
              data: {
                iteration: 2,
                hypotheses: [
                  {
                    statement: "Automated credential stuffing via proxy",
                    confidence: 0.92,
                    supporting_evidence_ids: ["ev_tx_1"],
                    contradicting_evidence_ids: [],
                  },
                ],
                unresolved_questions: [],
              },
            },
          ],
        }),
      });
    });

    await page.goto("/disputes/dsp_001");

    // Verify cold-hydrated Time-Travel Scrubber & Diff Panel render
    await expect(page.getByTestId("time-travel-scrubber")).toBeVisible();
    await expect(page.getByTestId("investigation-diff-panel")).toBeVisible();

    // Verify sticky citation pinning works across mouse leave
    const citeButton = page.locator("button", { hasText: "[cite: ev_tx_1]" }).first();
    await expect(citeButton).toBeVisible();
    await citeButton.click();
    await page.mouse.move(0, 0);
    await expect(page.locator("#evidence-card-ev_tx_1")).toContainText("Referenced");
  });

  test("telecom sandbox executes live classification and renders fraud probability", async ({
    page,
  }) => {
    await page.context().addCookies([
      {
        name: "sf_session",
        value: "e2e-mock-token",
        domain: "localhost",
        path: "/",
      },
    ]);

    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ username: "analyst", role: "analyst" }),
      });
    });

    await page.route("**/api/v1/telecom/metrics", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_requests: 120,
          blocked_count: 14,
          flagged_count: 8,
          allowed_count: 98,
          escalated_count: 3,
          block_rate: 0.116,
          latency_p50_ms: 1.8,
          latency_p95_ms: 4.2,
          latency_p99_ms: 7.9,
          recent_decisions: [],
        }),
      });
    });

    await page.route("**/api/v1/telecom/drift", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          overall_status: "healthy",
          sample_size: 120,
          evaluated_at: "2026-09-03T00:00:00Z",
          features: [],
        }),
      });
    });

    await page.route("**/api/v1/classify**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          event_id: "tel_e2e_99",
          decision: "BLOCK",
          fraud_probability: 0.964,
          risk_level: "CRITICAL",
          velocity_10s: 12,
          velocity_60s: 45,
          velocity_1h: 190,
          triggered_rules: ["IRSF_HIGH_COST_PREFIX_BURST"],
          shap_attributions: [
            { feature: "velocity_60s", value: 45, attribution: 0.42 },
          ],
          inference_latency_ms: 2.1,
          escalated_dispute_id: "dsp_irsf_99",
          escalated_investigation_id: "inv_irsf_99",
        }),
      });
    });

    await page.goto("/telecom");
    await expect(page.getByText("Interactive Event Classifier")).toBeVisible();
    await page.getByRole("button", { name: /Execute/i }).click();
    await expect(page.getByText("IRSF_HIGH_COST_PREFIX_BURST")).toBeVisible();
  });
});
