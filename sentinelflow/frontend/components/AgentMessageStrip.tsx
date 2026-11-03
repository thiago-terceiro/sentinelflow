import { memo } from "react";

type Props = {
  message: string | null;
  status: "IDLE" | "RUNNING" | "APPROVAL_REQUIRED" | "COMPLETED" | "FAILED";
};

const fallbackMessage = (status: Props["status"]) => {
  if (status === "APPROVAL_REQUIRED") {
    return "Awaiting reviewer approval";
  }
  if (status === "COMPLETED") {
    return "Investigation complete";
  }
  if (status === "FAILED") {
    return "Investigation failed";
  }
  if (status === "RUNNING") {
    return "Initializing investigation";
  }
  return "Ready to start";
};

export const AgentMessageStrip = memo(({ message, status }: Props) => {
  const isActive = status === "RUNNING" || status === "APPROVAL_REQUIRED";
  const isFinalized = status === "COMPLETED";
  const isFailed = status === "FAILED";

  const getDotStyle = () => {
    if (isFinalized) {
      return {
        background: "var(--success, #22c55e)",
        boxShadow: "0 0 8px rgba(34, 197, 94, 0.6)",
      };
    }
    if (isActive) {
      return {
        background: "var(--accent, #2563eb)",
        boxShadow: "0 0 8px rgba(37, 99, 235, 0.6)",
      };
    }
    if (isFailed) {
      return {
        background: "var(--danger, #ef4444)",
        boxShadow: "0 0 8px rgba(239, 68, 68, 0.6)",
      };
    }
    return {
      background: "rgba(15, 23, 42, 0.2)",
      boxShadow: "none",
    };
  };

  return (
    <section
      className="shell-card"
      style={{
        padding: "14px 18px",
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 10,
          height: 10,
          borderRadius: 999,
          flexShrink: 0,
          ...getDotStyle(),
        }}
      />
      <p
        style={{
          margin: 0,
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        Agent activity
      </p>
      <strong style={{ marginLeft: "auto", fontWeight: 600 }}>
        {message ?? fallbackMessage(status)}
      </strong>
    </section>
  );
});

AgentMessageStrip.displayName = "AgentMessageStrip";
