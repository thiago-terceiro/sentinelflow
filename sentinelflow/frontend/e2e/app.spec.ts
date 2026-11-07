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

  test("unauthenticated access to audit page renders access-restricted gate with sign-in link", async ({ page }) => {
    await page.goto("/audit");
    await expect(page.locator("h1")).toContainText("Access Restricted: Auditor or Admin Role Required");
    await expect(page.getByRole("link", { name: /Sign In as Auditor/i })).toHaveAttribute(
      "href",
      "/login?returnTo=/audit"
    );
  });

  test("unauthenticated access to disputes page renders access-restricted gate with sign-in link", async ({ page }) => {
    await page.goto("/disputes");
    await expect(page.locator("h2")).toContainText("Sign in to inspect seeded disputes");
    await expect(page.getByRole("link", { name: /Sign in to Investigation Console/i })).toHaveAttribute(
      "href",
      "/login?returnTo=/disputes"
    );
  });

  test("@visual login page visual appearance snapshot", async ({ page }) => {
    await page.goto("/login");
    await page.waitForSelector("form");
    await expect(page).toHaveScreenshot("login-page.png", {
      maxDiffPixelRatio: 0.1,
      animations: "disabled",
    });
  });

  test("investigation workbench supports cold-hydration, time-travel scrubbing, diffing, and sticky citation pinning", async ({
    page,
  }) => {
    await page.context().addCookies([
      {
        name: "sentinelflow_access_token",
        value: "dev-reviewer",
        domain: "localhost",
        path: "/",
      },
      {
        name: "sentinelflow_test_user",
        value: "reviewer:reviewer",
        domain: "localhost",
        path: "/",
      },
    ]);

    await page.route("**/app-api/disputes/dsp_001", async (route) => {
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

    await page.route("**/app-api/disputes/dsp_001/investigations/latest", async (route) => {
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
            conclusion: "Confirmed unauthorized charge [cite: ev_tx_1].",
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
              summary: "Anomaly detected in cardholder velocity [cite: ev_tx_1]",
              findings: ["Proxy IP detected"],
              confidence: 0.9,
              evidence_ids: ["ev_tx_1"],
              contradictions: [],
              recommended_followups: [],
            },
          ],
          hypotheses: [
            {
              statement: "Automated credential stuffing via proxy [cite: ev_tx_1]",
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
                    statement: "Automated credential stuffing via proxy [cite: ev_tx_1]",
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

    // Verify cold-hydrated Time-Travel Scrubber renders
    await expect(page.getByTestId("time-travel-scrubber")).toBeVisible();

    // Open Compare Iterations Diff Panel and verify it renders
    const compareBtn = page.getByRole("button", { name: /Compare Iterations/i });
    await expect(compareBtn).toBeVisible();
    await compareBtn.click();
    await expect(page.getByTestId("investigation-diff-panel")).toBeVisible();

    // Verify sticky citation pinning works across mouse leave
    const citeButton = page.locator("button", { hasText: /Evidence #ev_tx_1/i }).first();
    await expect(citeButton).toBeVisible();
    await citeButton.click();
    await page.mouse.move(0, 0);
    await expect(citeButton).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#evidence-ev_tx_1")).toBeVisible();
  });

  test("telecom sandbox executes live classification and renders fraud probability", async ({
    page,
  }) => {
    await page.route("**/app-api/telecom/classify**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "tel_e2e_99",
          sender: "+14155552671",
          recipient: "+14155559876",
          message: "URGENT: Your bank account has been locked.",
          carrier: "Verizon Wireless",
          verdict: "BLOCK",
          fraud_score: 0.964,
          latency_ms: 2.1,
          timestamp: "2026-09-03T00:00:00Z",
          signals: ["IRSF_HIGH_COST_PREFIX_BURST"],
          velocity: {
            count_10s: 12,
            count_60s: 45,
            count_1h: 190,
          },
        }),
      });
    });

    await page.goto("/telecom");
    await expect(page.getByText("Interactive SMS Gateway Tester")).toBeVisible();
    await page.getByRole("button", { name: /Run Real-Time Classification/i }).click();
    await expect(page.getByText("IRSF_HIGH_COST_PREFIX_BURST")).toBeVisible();
  });
});
