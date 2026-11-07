"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { useSentinelPulse } from "@/components/SentinelPulseProvider";
import {
  getDisputesCached,
  invalidateDisputesCache,
  peekDisputesCache,
} from "@/lib/disputesCache";
import type { DisputeSummary } from "@/lib/types";

const AuthErrorAlert = () => {
  const searchParams = useSearchParams();
  const authError = searchParams.get("auth_error");

  if (!authError) {
    return null;
  }

  return (
    <section
      className="shell-card"
      style={{
        padding: "18px 24px",
        borderColor: "rgba(158,47,40,0.25)",
        color: "var(--danger)",
        width: "100%",
        margin: 0,
      }}
    >
      Authentication failed: {authError}
    </section>
  );
};

const DisputesPage = () => {
  const { hasSession, clearSession } = useSentinelPulse();
  const [disputes, setDisputes] = useState<DisputeSummary[]>(() => peekDisputesCache() ?? []);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(() => !peekDisputesCache() && hasSession);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [resetCount, setResetCount] = useState<number>(0);

  useEffect(() => {
    const handleReset = () => {
      invalidateDisputesCache();
      setResetCount((prev) => prev + 1);
    };
    const handleInvalidate = () => {
      setResetCount((prev) => prev + 1);
    };
    window.addEventListener("sentinelflow:reset", handleReset);
    window.addEventListener("sentinelflow:disputes-invalidated", handleInvalidate);
    return () => {
      window.removeEventListener("sentinelflow:reset", handleReset);
      window.removeEventListener("sentinelflow:disputes-invalidated", handleInvalidate);
    };
  }, []);

  const loadDisputes = async (force = false): Promise<void> => {
    if (!hasSession) {
      setDisputes([]);
      setFetchError(null);
      setIsLoading(false);
      setIsRefreshing(false);
      return;
    }

    const cached = peekDisputesCache();
    if (!cached || force) {
      if (disputes.length === 0) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }
    }

    try {
      const nextDisputes = await getDisputesCached({ forceRefresh: force });
      setDisputes(nextDisputes);
      setFetchError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load disputes.";
      const isAuthError =
        message.toLowerCase().includes("auth") ||
        message.includes("401") ||
        message.includes("403");
      if (isAuthError) {
        setFetchError(null);
        clearSession();
      } else {
        setFetchError(message);
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (!hasSession) {
      setDisputes([]);
      setFetchError(null);
      setIsLoading(false);
      setIsRefreshing(false);
      return;
    }

    void loadDisputes(false);
  }, [hasSession, clearSession, resetCount]);

  const filteredDisputes = useMemo(() => {
    if (statusFilter === "ALL") {
      return disputes;
    }
    return disputes.filter((d) => d.status.toUpperCase() === statusFilter);
  }, [disputes, statusFilter]);

  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}
    >
      <section
        className="shell-card"
        style={{
          padding: "28px 32px",
          width: "100%",
          margin: 0,
          background:
            "linear-gradient(135deg, rgba(37, 99, 235, 0.07) 0%, rgba(201, 243, 106, 0.05) 100%)",
          border: "1px solid var(--panel-border)",
        }}
      >
        {/* Line 1: Stage 2 Badge */}
        <div style={{ marginBottom: 8 }}>
          <span
            style={{
              display: "inline-block",
              fontSize: 11,
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              padding: "4px 10px",
              borderRadius: 6,
              background: "var(--accent-soft, rgba(201, 243, 106, 0.15))",
              color: "var(--accent, #2563eb)",
              border: "1px solid var(--panel-border)",
            }}
          >
            Stage 2: Asynchronous Multi-Agent Copilot
          </span>
        </div>

        {/* Line 2: Investigation Status */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 10,
          }}
        >
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: "#22c55e",
              boxShadow: "0 0 8px #22c55e",
            }}
          />
          <span
            style={{
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "0.08em",
              color: "var(--muted)",
              textTransform: "uppercase",
            }}
          >
            LANGGRAPH + GPT-4 INVESTIGATION ACTIVE
          </span>
        </div>

        <h1 style={{ margin: "4px 0 12px", fontSize: "clamp(1.85rem, 4.5vw, 3.4rem)", letterSpacing: "-0.03em" }}>
          ⚡ SentinelFlow: Seeded Disputes Workbench
        </h1>

        <p style={{ maxWidth: 820, margin: 0, color: "var(--muted)", fontSize: 15, lineHeight: 1.6 }}>
          SentinelFlow coordinates parallel agent evidence gathering, deterministic risk scoring,
          and human-in-the-loop steering. All decisions and time-travel revisions are securely
          anchored to a SHA-256 tamper-proof ledger.
        </p>
      </section>

      <div id="seeded-disputes-section" style={{ display: "flex", flexDirection: "column", gap: 24, width: "100%" }}>
        <Suspense fallback={null}>
          <AuthErrorAlert />
        </Suspense>

        {!hasSession ? (
          <section
            className="shell-card"
            style={{
              padding: "32px 28px",
              width: "100%",
              margin: 0,
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--accent)",
                }}
              >
                Authenticated Workbench Access
              </span>
              <h2 style={{ margin: "6px 0 8px", fontSize: 22 }}>
                Sign in to inspect seeded disputes &amp; live LangGraph investigations
              </h2>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: 14, maxWidth: 680, lineHeight: 1.6 }}>
                Access the 5 showcase dispute archetypes (including pre-hydrated multi-iteration
                time-travel runs and human-in-the-loop interrupt checkpoints) using a role-based test
                account, or inspect real-time SMS traffic in SentinelPulse.
              </p>
            </div>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <Link
                href="/login?returnTo=/disputes"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: 44,
                  padding: "10px 22px",
                  borderRadius: "var(--card-radius, 8px)",
                  background: "var(--accent)",
                  color: "var(--accent-ink, #ffffff)",
                  fontWeight: 700,
                  fontSize: 13,
                  textDecoration: "none",
                }}
              >
                Sign in to Investigation Console →
              </Link>
              <Link
                href="/"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: 44,
                  padding: "10px 20px",
                  borderRadius: "var(--card-radius, 8px)",
                  border: "1px solid var(--panel-border)",
                  background: "rgba(255,255,255,0.04)",
                  color: "var(--foreground)",
                  fontWeight: 600,
                  fontSize: 13,
                  textDecoration: "none",
                }}
              >
                📡 Explore SentinelPulse Live Gateway
              </Link>
            </div>
          </section>
        ) : (
          <>
            {fetchError ? (
              <section
                className="shell-card"
                style={{
                  padding: "18px 24px",
                  borderColor: "rgba(158,47,40,0.25)",
                  color: "var(--danger)",
                  width: "100%",
                  margin: 0,
                }}
              >
                {fetchError}
              </section>
            ) : null}

            <section className="shell-card" style={{ padding: "24px 28px", width: "100%", margin: 0 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 12,
                  paddingBottom: 14,
                  marginBottom: 14,
                  borderBottom: "1px solid var(--panel-border)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <h2 style={{ margin: 0, fontSize: 20 }}>Seeded disputes</h2>
                  <span
                    style={{
                      color: "var(--muted)",
                      fontSize: 12,
                      padding: "2px 8px",
                      borderRadius: 999,
                      border: "1px solid var(--panel-border)",
                    }}
                  >
                    {filteredDisputes.length} cases
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      void loadDisputes(true);
                    }}
                    disabled={isRefreshing || isLoading}
                    aria-label="Refresh disputes list"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      minHeight: 44,
                      padding: "6px 12px",
                      borderRadius: 6,
                      border: "1px solid var(--panel-border)",
                      background: "transparent",
                      color: "var(--foreground)",
                      cursor: isRefreshing || isLoading ? "wait" : "pointer",
                      fontSize: 12,
                      fontWeight: 600,
                      transition: "all 0.15s ease",
                    }}
                    className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                  >
                    <span
                      style={{
                        display: "inline-block",
                        transform: isRefreshing ? "rotate(180deg)" : "none",
                        transition: "transform 0.4s ease",
                      }}
                      aria-hidden="true"
                    >
                      🔄
                    </span>
                    <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
                  </button>
                </div>

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {[
                    { key: "ALL", label: "All" },
                    { key: "OPEN", label: "Open" },
                    { key: "UNDER_REVIEW", label: "Under Review" },
                    { key: "COMPLETED", label: "Completed" },
                  ].map((pill) => {
                    const active = statusFilter === pill.key;
                    return (
                      <button
                        key={pill.key}
                        type="button"
                        onClick={() => setStatusFilter(pill.key)}
                        style={{
                          fontSize: 12,
                          padding: "8px 14px",
                          minHeight: 44,
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          borderRadius: 999,
                          border: active
                            ? "1px solid var(--accent)"
                            : "1px solid var(--panel-border)",
                          background: active
                            ? "var(--accent-soft, rgba(37, 99, 235, 0.12))"
                            : "transparent",
                          color: active ? "var(--accent)" : "var(--muted)",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {pill.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div
                role="region"
                aria-label="Seeded disputes queue"
                tabIndex={0}
                style={{
                  display: "grid",
                  gap: 12,
                  width: "100%",
                  maxHeight: 460,
                  overflowY: "auto",
                  paddingRight: 4,
                }}
              >
                {isLoading ? (
                  <p style={{ margin: 0, color: "var(--muted)" }}>Loading disputes...</p>
                ) : null}
                {!isLoading && filteredDisputes.length === 0 ? (
                  <p style={{ margin: 0, color: "var(--muted)" }}>
                    No disputes matching current filter.
                  </p>
                ) : null}
                {filteredDisputes.map((dispute) => (
                  <Link
                    key={dispute.id}
                    href={`/disputes/${dispute.id}`}
                    className="shell-card dispute-card-item"
                    style={{
                      padding: "16px 20px",
                      display: "block",
                      width: "100%",
                      textDecoration: "none",
                      margin: 0,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        flexWrap: "wrap",
                        gap: 12,
                      }}
                    >
                      <div style={{ minWidth: 0, flex: "1 1 200px" }}>
                        <strong style={{ fontSize: 15 }}>{dispute.case_code}</strong>
                        <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 13 }}>
                          {dispute.title}
                        </p>
                      </div>
                      <div style={{ textAlign: "right", color: "var(--muted)", fontSize: 13 }}>
                        <div style={{ fontWeight: 600, color: "var(--foreground)" }}>
                          {dispute.currency} {dispute.amount.toFixed(2)}
                        </div>
                        <div style={{ marginTop: 4 }}>{dispute.status}</div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
};

export default DisputesPage;
