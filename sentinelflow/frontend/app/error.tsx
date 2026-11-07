"use client";

const GlobalError = ({ reset }: { error: Error; reset: () => void }) => {
  return (
    <main style={{ padding: "48px 0" }}>
      <section className="shell-card" style={{ padding: 28 }}>
        <h1>Console error</h1>
        <p>The route failed to render. Retry the request.</p>
        <button
          type="button"
          onClick={() => reset()}
          style={{
            minHeight: 44,
            border: 0,
            borderRadius: 8,
            padding: "12px 18px",
            background: "var(--accent, #1e3a8a)",
            color: "var(--accent-ink, #ffffff)",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      </section>
    </main>
  );
};

export default GlobalError;
