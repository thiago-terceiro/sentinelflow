"use client";

const GlobalError = ({ reset }: { error: Error; reset: () => void }) => {
    return (
        <main style={{ padding: "48px 0" }}>
            <section className="shell-card" style={{ padding: 28 }}>
                <h1>Console error</h1>
                <p>The route failed to render. Retry the request.</p>
                <button
                    onClick={() => reset()}
                    style={{ border: 0, borderRadius: 999, padding: "12px 18px", background: "var(--accent)", color: "white" }}
                >
                    Retry
                </button>
            </section>
        </main>
    );
};

export default GlobalError;
