import Link from "next/link";

import { InvestigationConsole } from "@/components/InvestigationConsole";

type Props = {
  params: Promise<{ disputeId: string }>;
};

const DisputePage = async ({ params }: Props) => {
  const { disputeId } = await params;
  return (
    <main>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 18,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <Link
          href="/"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            color: "var(--muted)",
            whiteSpace: "nowrap",
            textDecoration: "none",
            fontWeight: 500,
            fontSize: 14,
          }}
        >
          ← Back to disputes
        </Link>

        <Link
          href="/telecom?filter=ESCALATED#inspection-feed"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            color: "var(--accent, #2563eb)",
            whiteSpace: "nowrap",
            textDecoration: "none",
            fontWeight: 600,
            fontSize: 13,
            padding: "6px 14px",
            borderRadius: "var(--card-radius, 6px)",
            border: "1px solid var(--panel-border)",
            background: "var(--panel, #ffffff)",
            transition: "all 0.15s ease",
          }}
        >
          See on SentinelPulse →
        </Link>
      </div>
      <InvestigationConsole disputeId={disputeId} />
    </main>
  );
};

export default DisputePage;
