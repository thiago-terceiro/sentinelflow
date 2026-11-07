import Link from "next/link";

import { DisputeBreadcrumbNav } from "@/components/DisputeBreadcrumbNav";
import { InvestigationConsole } from "@/components/InvestigationConsole";

type Props = {
  params: Promise<{ disputeId: string }>;
  searchParams?: Promise<{ from?: string }>;
};

const DisputePage = async ({ params, searchParams }: Props) => {
  const { disputeId } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const fromPulse = resolvedSearchParams?.from === "pulse";

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
        <DisputeBreadcrumbNav initialFromPulse={fromPulse} />

        <Link
          href="/?filter=ESCALATED#inspection-feed"
          style={{
            display: "inline-flex",
            alignItems: "center",
            minHeight: 44,
            gap: 6,
            color: "var(--accent, #2563eb)",
            whiteSpace: "nowrap",
            textDecoration: "none",
            fontWeight: 600,
            fontSize: 13,
            padding: "8px 16px",
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
