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
    <nav className="app-nav-links">
      <Link
        href="/"
        prefetch={true}
        className="app-nav-link"
        style={{
          color: isTelecomActive ? "var(--foreground)" : "var(--muted)",
          textDecoration: "none",
          fontWeight: isTelecomActive ? 700 : 600,
          minHeight: 44,
          padding: "8px 14px",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        <span>
          <span className="nav-icon">📡 </span>
          <span className="nav-label-title">SentinelPulse</span>
        </span>
        {isTelecomActive ? <span className="nav-dash" aria-hidden="true" /> : null}
      </Link>

      <Link
        href="/disputes"
        prefetch={true}
        className="app-nav-link"
        style={{
          color: isDisputesActive ? "var(--foreground)" : "var(--muted)",
          textDecoration: "none",
          fontWeight: isDisputesActive ? 700 : 600,
          minHeight: 44,
          padding: "8px 14px",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        <span>
          <span className="nav-icon">⚡ </span>
          <span className="nav-label-title">SentinelFlow</span>
        </span>
        {isDisputesActive ? <span className="nav-dash" aria-hidden="true" /> : null}
      </Link>

      {canSeeAudit ? (
        <Link
          href="/audit"
          prefetch={true}
          className="app-nav-link"
          style={{
            color: isAuditActive ? "var(--foreground)" : "var(--muted)",
            textDecoration: "none",
            fontWeight: isAuditActive ? 700 : 600,
            minHeight: 44,
            padding: "8px 14px",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          <span>
            <span className="nav-icon">🔒 </span>
            <span className="nav-label-title">Audit Ledger</span>
          </span>
          {isAuditActive ? <span className="nav-dash" aria-hidden="true" /> : null}
        </Link>
      ) : null}
    </nav>
  );
};
