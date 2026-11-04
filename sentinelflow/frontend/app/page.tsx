"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { useSentinelPulse } from "@/components/SentinelPulseProvider";
import { listDisputes } from "@/lib/api";
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

const HomePage = () => {
  const { hasSession } = useSentinelPulse();
  const [disputes, setDisputes] = useState<DisputeSummary[]>([]);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  useEffect(() => {
    if (!hasSession) {
      setDisputes([]);
      setFetchError(null);
      setIsLoading(false);
      return;
    }

    const loadDisputes = async (): Promise<void> => {
      setIsLoading(true);
      try {
        const nextDisputes = await listDisputes();
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
        } else {
          setFetchError(message);
        }
      } finally {
        setIsLoading(false);
      }
    };

    void loadDisputes();
  }, [hasSession]);

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
      <section className="shell-card" style={{ padding: "28px 32px", width: "100%", margin: 0 }}>
        <h1 style={{ margin: "8px 0 12px", fontSize: "clamp(1.85rem, 4.5vw, 3.6rem)" }}>
          SentinelFlow
        </h1>
        <p style={{ maxWidth: 780, margin: 0, color: "var(--muted)", lineHeight: 1.6 }}>
          SentinelFlow is an autonomous AI dispute investigation copilot built on LangGraph that
          coordinates parallel multi-agent evidence collection, deterministic risk scoring, and
          human-in-the-loop steering. Paired with SentinelPulse, a sub-15ms telecom fraud
          intelligence gateway powered by ONNX Runtime CPU.
        </p>
      </section>

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
              href="/login?returnTo=/"
              style={{
                display: "inline-flex",
                alignItems: "center",
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
              href="/telecom"
              style={{
                display: "inline-flex",
                alignItems: "center",
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
                        fontSize: 11,
                        padding: "4px 10px",
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
    </main>
  );
};

export default HomePage;
