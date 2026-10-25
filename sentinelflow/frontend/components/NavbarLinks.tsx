"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface Props {
  hasSession: boolean;
  userRole: string | null;
}

export const NavbarLinks = ({ hasSession, userRole }: Props) => {
  const pathname = usePathname();

  const isDisputesActive = pathname === "/" || pathname.startsWith("/disputes");
  const isTelecomActive = pathname.startsWith("/telecom");
  const isAuditActive = pathname.startsWith("/audit");

  // Auditor Portal is only visible if user is authenticated and has auditor or admin role
  const canSeeAudit = hasSession && (userRole === "auditor" || userRole === "admin");

  return (
    <nav style={{ display: "flex", gap: 18, fontSize: 13, alignItems: "center" }}>
      <Link
        href="/"
        style={{
          color: isDisputesActive ? "var(--foreground)" : "var(--muted)",
          textDecoration: "none",
          fontWeight: isDisputesActive ? 600 : 500,
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "center",
          position: "relative",
          paddingBottom: 2,
        }}
      >
        <span>Disputes</span>
        {isDisputesActive ? <span className="nav-dash" aria-hidden="true" /> : null}
      </Link>

      <Link
        href="/telecom"
        style={{
          color: isTelecomActive ? "var(--foreground)" : "var(--muted)",
          textDecoration: "none",
          fontWeight: isTelecomActive ? 600 : 500,
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "center",
          position: "relative",
          paddingBottom: 2,
        }}
      >
        <span>
          <span className="nav-icon">📡 </span>SentinelPulse Gateway
        </span>
        {isTelecomActive ? <span className="nav-dash" aria-hidden="true" /> : null}
      </Link>

      {canSeeAudit ? (
        <Link
          href="/audit"
          style={{
            color: isAuditActive ? "var(--foreground)" : "var(--muted)",
            textDecoration: "none",
            fontWeight: isAuditActive ? 600 : 500,
            display: "inline-flex",
            flexDirection: "column",
            alignItems: "center",
            position: "relative",
            paddingBottom: 2,
          }}
        >
          <span>
            <span className="nav-icon">🛡️ </span>Auditor Portal
          </span>
          {isAuditActive ? <span className="nav-dash" aria-hidden="true" /> : null}
        </Link>
      ) : null}
    </nav>
  );
};
