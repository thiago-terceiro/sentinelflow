"use client";

type StageKey = "intake" | "investigate" | "collect" | "synthesize" | "approval" | "finalize";

type StageConfig = {
    key: StageKey;
    label: string;
    sublabel: string;
};

const STAGES: StageConfig[] = [
    { key: "intake", label: "Intake", sublabel: "State init" },
    { key: "investigate", label: "Investigate", sublabel: "LLM reasoning" },
    { key: "collect", label: "Collect", sublabel: "Tools & analyzers" },
    { key: "synthesize", label: "Synthesize", sublabel: "Evidence synthesis" },
    { key: "approval", label: "Approval", sublabel: "Human interrupt" },
    { key: "finalize", label: "Finalize", sublabel: "Audit & commit" },
];

type Props = {
    currentPhase?: StageKey;
    status: string;
    reviewerGuidance?: string | null;
};

export const LangGraphProgress = ({ currentPhase = "intake", status, reviewerGuidance }: Props) => {
    const stageOrder: Record<StageKey, number> = {
        intake: 0,
        investigate: 1,
        collect: 2,
        synthesize: 3,
        approval: 4,
        finalize: 5,
    };

    const currentIndex = stageOrder[currentPhase] ?? 0;
    const isCompleted = status === "COMPLETED";
    const isFailed = status === "FAILED";

    return (
        <div className="shell-card" style={{ padding: "20px 24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div>
                    <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)" }}>
                        LangGraph Execution Pipeline
                    </span>
                    <h3 style={{ margin: "2px 0 0 0", fontSize: 16, fontWeight: 600 }}>
                        Active Graph State: <span style={{ color: "var(--accent)" }}>{currentPhase.toUpperCase()}</span>
                    </h3>
                </div>
                {reviewerGuidance ? (
                    <span
                        style={{
                            padding: "4px 10px",
                            borderRadius: 999,
                            fontSize: 11,
                            background: "rgba(99,102,241,0.15)",
                            color: "#818cf8",
                            border: "1px solid rgba(99,102,241,0.3)",
                        }}
                    >
                        ⟲ Human Steering Loop Active
                    </span>
                ) : null}
            </div>

            <div style={{ display: "flex", alignItems: "center", position: "relative", gap: 8, overflowX: "auto" }}>
                {STAGES.map((stage, idx) => {
                    const isCurrent = currentPhase === stage.key && !isCompleted;
                    const isPast = idx < currentIndex || isCompleted;

                    let badgeColor = "var(--panel-border)";
                    let textColor = "var(--muted)";
                    let dotBg = "rgba(255,255,255,0.1)";

                    if (isFailed && isCurrent) {
                        badgeColor = "var(--danger)";
                        textColor = "var(--danger)";
                        dotBg = "var(--danger)";
                    } else if (isCurrent) {
                        badgeColor = "var(--accent)";
                        textColor = "var(--accent)";
                        dotBg = "var(--accent)";
                    } else if (isPast) {
                        badgeColor = "var(--success)";
                        textColor = "var(--foreground)";
                        dotBg = "var(--success)";
                    }

                    return (
                        <div
                            key={stage.key}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                flex: 1,
                                minWidth: 110,
                            }}
                        >
                            <div
                                style={{
                                    display: "flex",
                                    flexDirection: "column",
                                    alignItems: "flex-start",
                                    padding: "8px 12px",
                                    borderRadius: 10,
                                    border: `1px solid ${badgeColor}`,
                                    background: isCurrent ? "rgba(99,102,241,0.06)" : "transparent",
                                    width: "100%",
                                }}
                            >
                                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                    <span
                                        style={{
                                            width: 8,
                                            height: 8,
                                            borderRadius: "50%",
                                            background: dotBg,
                                            display: "inline-block",
                                        }}
                                    />
                                    <span style={{ fontSize: 13, fontWeight: 600, color: textColor }}>
                                        {stage.label}
                                    </span>
                                </div>
                                <span style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                                    {stage.sublabel}
                                </span>
                            </div>
                            {idx < STAGES.length - 1 ? (
                                <span style={{ color: "var(--muted)", margin: "0 4px", fontSize: 14 }}>
                                    →
                                </span>
                            ) : null}
                        </div>
                    );
                })}
            </div>

            {reviewerGuidance ? (
                <div
                    style={{
                        marginTop: 14,
                        padding: "10px 14px",
                        borderRadius: 8,
                        background: "rgba(99,102,241,0.06)",
                        borderLeft: "3px solid #818cf8",
                        fontSize: 12,
                    }}
                >
                    <strong style={{ color: "#a5b4fc" }}>Reviewer Steering Guidance Applied: </strong>
                    <span style={{ color: "var(--foreground)" }}>{reviewerGuidance}</span>
                </div>
            ) : null}
        </div>
    );
};
