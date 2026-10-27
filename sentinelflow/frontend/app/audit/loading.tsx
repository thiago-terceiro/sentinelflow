const Loading = () => {
  return (
    <main aria-busy="true" aria-live="polite" style={{ padding: "32px 0" }}>
      <div className="shell-card" style={{ padding: 28, display: "grid", gap: 12 }}>
        <span style={{ fontSize: 12, textTransform: "uppercase", color: "var(--muted)" }}>
          SentinelFlow Workbench
        </span>
        <p style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
          Loading workspace telemetry...
        </p>
      </div>
    </main>
  );
};

export default Loading;
