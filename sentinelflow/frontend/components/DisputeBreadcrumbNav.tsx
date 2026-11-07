"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Props = {
  initialFromPulse?: boolean;
};

export const DisputeBreadcrumbNav = ({ initialFromPulse = false }: Props) => {
  const [fromPulse, setFromPulse] = useState(initialFromPulse);

  useEffect(() => {
    if (initialFromPulse) {
      return;
    }
    try {
      if (typeof document !== "undefined" && document.referrer) {
        const refUrl = new URL(document.referrer);
        if (refUrl.pathname === "/" || refUrl.pathname.startsWith("/telecom")) {
          setFromPulse(true);
        }
      }
    } catch {
      // In SSR or non-browser environments
    }
  }, [initialFromPulse]);

  const label = fromPulse ? "To Disputes" : "Back to disputes";

  return (
    <Link
      href="/disputes"
      aria-label={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        minHeight: 44,
        padding: "8px 14px",
        gap: 6,
        color: "var(--muted)",
        whiteSpace: "nowrap",
        textDecoration: "none",
        fontWeight: 500,
        fontSize: 14,
      }}
      className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
    >
      ← {label}
    </Link>
  );
};
