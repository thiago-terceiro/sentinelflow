"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface Props {
  hasSession: boolean;
  userRole: string | null;
}

export const NavbarLinks = ({ hasSession, userRole }: Props) => {
  const pathname = usePathname();

  const isTelecomActive = pathname === "/" || pathname.startsWith("/telecom");
  const isDisputesActive = pathname.startsWith("/disputes");
  const isAuditActive = pathname.startsWith("/audit");

  // Auditor Portal is only visible if user is authenticated and has auditor or admin role
  const canSeeAudit = hasSession && (userRole === "auditor" || userRole === "admin");

  return (
    <nav style={{ display: "flex", gap: 12, fontSize: 13, alignItems: "center", flexWrap: "wrap" }}>
      <Link
        href="/"
        prefetch={true}
        style={{
          color: isTelecomActive ? "var(--foreground)" : "var(--muted)",
          textDecoration: "none",
          fontWeight: isTelecomActive ? 700 : 600,
          minHeight: 44,
          padding: "8px 12px",
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <span>
          <span className="nav-icon">📡 </span>SentinelPulse (Wire Ingress)
        </span>
        {isTelecomActive ? <span className="nav-dash" aria-hidden="true" /> : null}
      </Link>

      <Link
        href="/disputes"
        prefetch={true}
        style={{
          color: isDisputesActive ? "var(--foreground)" : "var(--muted)",
          textDecoration: "none",
          fontWeight: isDisputesActive ? 700 : 600,
          minHeight: 44,
          padding: "8px 12px",
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <span>
          <span className="nav-icon">⚡ </span>SentinelFlow (Disputes &amp; Multi-Agent Copilot)
        </span>
        {isDisputesActive ? <span className="nav-dash" aria-hidden="true" /> : null}
      </Link>

      {canSeeAudit ? (
        <Link
          href="/audit"
          prefetch={true}
          style={{
            color: isAuditActive ? "var(--foreground)" : "var(--muted)",
            textDecoration: "none",
            fontWeight: isAuditActive ? 700 : 600,
            minHeight: 44,
            padding: "8px 12px",
            display: "inline-flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
          }}
        >
          <span>
            <span className="nav-icon">🔒 </span>Audit Ledger (Tamper-Proof Ledger)
          </span>
          {isAuditActive ? <span className="nav-dash" aria-hidden="true" /> : null}
        </Link>
      ) : null}
    </nav>
  );
};
