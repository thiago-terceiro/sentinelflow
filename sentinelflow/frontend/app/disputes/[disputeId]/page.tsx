import Link from "next/link";

import { InvestigationConsole } from "@/components/InvestigationConsole";

type Props = {
  params: Promise<{ disputeId: string }>;
};

const DisputePage = async ({ params }: Props) => {
  const { disputeId } = await params;
  return (
    <main>
      <Link
        href="/"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 18,
          color: "var(--muted)",
          whiteSpace: "nowrap",
          textDecoration: "none",
          fontWeight: 500,
          fontSize: 14,
        }}
      >
        ← Back to disputes
      </Link>
      <InvestigationConsole disputeId={disputeId} />
    </main>
  );
};

export default DisputePage;
