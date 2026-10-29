"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { listDisputes } from "@/lib/api";
import type { DisputeSummary } from "@/lib/types";

const HomePage = () => {
  const [disputes, setDisputes] = useState<DisputeSummary[]>([]);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const searchParams = useSearchParams();

  const authError = useMemo(() => searchParams.get("auth_error"), [searchParams]);

  useEffect(() => {
    const loadDisputes = async (): Promise<void> => {
      setIsLoading(true);
      try {
        const nextDisputes = await listDisputes();
        setDisputes(nextDisputes);
        setFetchError(null);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to load disputes.";
        setFetchError(message);
      } finally {
        setIsLoading(false);
      }
    };

    void loadDisputes();
  }, []);

  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}
    >
      <section className="shell-card" style={{ padding: "28px 32px", width: "100%", margin: 0 }}>
        <h1 style={{ margin: "8px 0 12px", fontSize: "clamp(2.4rem, 4.5vw, 4rem)" }}>
          SentinelFlow
        </h1>
        <p style={{ maxWidth: 780, margin: 0, color: "var(--muted)", lineHeight: 1.6 }}>
          SentinelFlow is an autonomous AI dispute investigation copilot built on LangGraph that
          coordinates parallel multi-agent evidence collection, deterministic risk scoring, and
          human-in-the-loop steering. Paired with SentinelPulse, a sub-15ms telecom fraud
          intelligence gateway powered by ONNX Runtime CPU.
        </p>
      </section>

      {authError ? (
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
      ) : null}

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
          {fetchError.toLowerCase().includes("authentication") ||
          fetchError.toLowerCase().includes("unauthenticated") ? (
            <span style={{ display: "block", marginTop: 10 }}>
              <Link href="/login" style={{ color: "var(--danger)", textDecoration: "underline" }}>
                Continue with sign-in
              </Link>
            </span>
          ) : null}
        </section>
      ) : null}

      <section className="shell-card" style={{ padding: "28px 32px", width: "100%", margin: 0 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            marginBottom: 20,
          }}
        >
          <h2 style={{ margin: 0, fontSize: 20 }}>Seeded disputes</h2>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>{disputes.length} cases</span>
        </div>
        <div style={{ display: "grid", gap: 14, width: "100%" }}>
          {isLoading ? <p style={{ margin: 0, color: "var(--muted)" }}>Loading disputes...</p> : null}
          {!isLoading && disputes.length === 0 ? (
            <p style={{ margin: 0, color: "var(--muted)" }}>No disputes available.</p>
          ) : null}
          {disputes.map((dispute) => (
            <Link
              key={dispute.id}
              href={`/disputes/${dispute.id}`}
              className="shell-card dispute-card-item"
              style={{
                padding: "18px 24px",
                display: "block",
                width: "100%",
                textDecoration: "none",
                margin: 0,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                <div>
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
    </main>
  );
};

export default HomePage;
