"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { listDisputes } from "@/lib/api";
import type { DisputeSummary } from "@/lib/types";

export default function HomePage() {
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
        <main style={{ padding: "40px 0 80px" }}>
            <section className="shell-card" style={{ padding: 32, marginBottom: 22 }}>
                <p style={{ margin: 0, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Operations console
                </p>
                <h1 style={{ marginBottom: 12, fontSize: "clamp(2.6rem, 5vw, 5rem)" }}>SentinelFlow</h1>
                <p style={{ maxWidth: 700, color: "var(--muted)" }}>
                    Evidence-grounded dispute investigations with deterministic risk scoring and reviewer approval for high-impact outcomes.
                </p>
            </section>

            {authError ? (
                <section className="shell-card" style={{ padding: 18, borderColor: "rgba(158,47,40,0.25)", color: "var(--danger)", marginBottom: 22 }}>
                    Authentication failed: {authError}
                </section>
            ) : null}

            {fetchError ? (
                <section className="shell-card" style={{ padding: 18, borderColor: "rgba(158,47,40,0.25)", color: "var(--danger)" }}>
                    {fetchError}
                    {fetchError.toLowerCase().includes("authentication") || fetchError.toLowerCase().includes("unauthenticated") ? (
                        <span style={{ display: "block", marginTop: 10 }}>
                            <Link href="/login" style={{ color: "var(--danger)", textDecoration: "underline" }}>
                                Continue with sign-in
                            </Link>
                        </span>
                    ) : null}
                </section>
            ) : null}

            <section className="shell-card" style={{ padding: 28 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                    <h2>Seeded disputes</h2>
                    <span style={{ color: "var(--muted)" }}>{disputes.length} cases</span>
                </div>
                <div style={{ display: "grid", gap: 16 }}>
                    {isLoading ? <p>Loading disputes...</p> : null}
                    {!isLoading && disputes.length === 0 ? <p>No disputes available.</p> : null}
                    {disputes.map((dispute) => (
                        <Link
                            key={dispute.id}
                            href={`/disputes/${dispute.id}`}
                            className="shell-card"
                            style={{ padding: 20, display: "block" }}
                        >
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                                <div>
                                    <strong>{dispute.case_code}</strong>
                                    <p style={{ marginBottom: 0 }}>{dispute.title}</p>
                                </div>
                                <div style={{ textAlign: "right", color: "var(--muted)" }}>
                                    <div>{dispute.currency} {dispute.amount.toFixed(2)}</div>
                                    <div>{dispute.status}</div>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            </section>
        </main>
    );
}
