import Link from "next/link";

import { InvestigationConsole } from "@/components/InvestigationConsole";

type Props = {
    params: Promise<{ disputeId: string }>;
};

export default async function DisputePage({ params }: Props) {
    const { disputeId } = await params;
    return (
        <main style={{ padding: "32px 0 80px" }}>
            <Link href="/" style={{ display: "inline-block", marginBottom: 18, color: "var(--muted)" }}>
                Back to disputes
            </Link>
            <InvestigationConsole disputeId={disputeId} />
        </main>
    );
}
