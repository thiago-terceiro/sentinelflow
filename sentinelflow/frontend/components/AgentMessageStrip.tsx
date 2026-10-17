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

export const AgentMessageStrip = ({ message, status }: Props) => {
  const isActive = status === "RUNNING" || status === "APPROVAL_REQUIRED";

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
          background: isActive ? "var(--accent)" : "rgba(255,255,255,0.18)",
          flexShrink: 0,
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
};
