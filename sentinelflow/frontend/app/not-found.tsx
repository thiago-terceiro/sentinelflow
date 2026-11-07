import Link from "next/link";

const NotFound = () => {
  return (
    <main style={{ padding: "32px 0" }}>
      <div className="shell-card" style={{ padding: 28, display: "grid", gap: 12 }}>
        <span style={{ fontSize: 12, textTransform: "uppercase", color: "var(--muted)" }}>
          404 · Resource Not Found
        </span>
        <h1 style={{ margin: 0, fontSize: 22 }}>Requested view could not be located</h1>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
          Verify the case or investigation identifier and return to the primary console.
        </p>
        <div>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              minHeight: 44,
              padding: "10px 18px",
              borderRadius: 8,
              background: "var(--accent, #1e3a8a)",
              color: "var(--accent-ink, #ffffff)",
              fontWeight: 700,
              textDecoration: "none",
              fontSize: 13,
            }}
          >
            ← Return to SentinelFlow Console
          </Link>
        </div>
      </div>
    </main>
  );
};

export default NotFound;
