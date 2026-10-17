"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { TEST_AUTH_USERS, sanitizeReturnPath, type TestAuthRole } from "@/lib/testAuth";

const errorMessages: Record<string, string> = {
  invalid_credentials: "Invalid username, password, or role.",
  missing_credentials: "Username, password, and role are required.",
  oidc_disabled: "OIDC login is disabled in this test mode.",
};

const LoginPage = () => {
  const searchParams = useSearchParams();
  const safeReturnTo = useMemo(
    () => sanitizeReturnPath(searchParams.get("returnTo")),
    [searchParams]
  );
  const message = useMemo(() => {
    const error = searchParams.get("error");
    if (!error) {
      return null;
    }
    return errorMessages[error] ?? "Sign-in failed.";
  }, [searchParams]);

  const [role, setRole] = useState<TestAuthRole>("investigator");
  const [username, setUsername] = useState<string>("investigator");
  const [password, setPassword] = useState<string>("investigator123");
  const [copiedRole, setCopiedRole] = useState<TestAuthRole | null>(null);

  const applyAccount = (
    nextRole: TestAuthRole,
    nextUsername: string,
    nextPassword: string
  ): void => {
    setRole(nextRole);
    setUsername(nextUsername);
    setPassword(nextPassword);
  };

  const copyAccount = async (
    nextRole: TestAuthRole,
    nextUsername: string,
    nextPassword: string
  ): Promise<void> => {
    const content = `role=${nextRole}\nusername=${nextUsername}\npassword=${nextPassword}`;
    await navigator.clipboard.writeText(content);
    setCopiedRole(nextRole);
    window.setTimeout(
      () => setCopiedRole((current) => (current === nextRole ? null : current)),
      1200
    );
  };

  return (
    <main style={{ padding: "40px 0 80px" }}>
      <section className="shell-card" style={{ padding: 28, maxWidth: 720, margin: "0 auto" }}>
        <p
          style={{
            margin: 0,
            color: "var(--muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Test access
        </p>
        <h1 style={{ marginTop: 12 }}>Sign in</h1>
        <p style={{ color: "var(--muted)", maxWidth: 620 }}>
          Local testing mode with hardcoded users. Choose a role and use the matching credentials to
          start the console.
        </p>

        {message ? (
          <div
            className="shell-card"
            style={{
              marginTop: 16,
              padding: 14,
              borderColor: "rgba(158,47,40,0.25)",
              color: "var(--danger)",
            }}
          >
            {message}
          </div>
        ) : null}

        <form
          action="/api/auth/login"
          method="POST"
          style={{ display: "grid", gap: 14, marginTop: 20 }}
        >
          <input type="hidden" name="returnTo" value={safeReturnTo} />

          <label style={{ display: "grid", gap: 6 }}>
            <span>Role</span>
            <select
              name="role"
              value={role}
              onChange={(event) => setRole(event.target.value as TestAuthRole)}
              style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
            >
              {TEST_AUTH_USERS.map((user) => (
                <option key={user.role} value={user.role}>
                  {user.label}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span>Username</span>
            <input
              name="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span>Password</span>
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
            />
          </label>

          <button
            type="submit"
            style={{
              marginTop: 6,
              padding: "10px 16px",
              borderRadius: 8,
              border: "1px solid var(--border-strong)",
              background: "var(--accent)",
              color: "white",
              cursor: "pointer",
              width: "fit-content",
            }}
          >
            Sign in
          </button>
        </form>

        <div className="shell-card" style={{ padding: 16, marginTop: 20 }}>
          <strong>Test accounts</strong>
          <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
            {TEST_AUTH_USERS.map((user) => (
              <div
                key={`${user.role}-credentials`}
                style={{
                  display: "grid",
                  gap: 8,
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  padding: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <strong>{user.label}</strong>
                  {copiedRole === user.role ? (
                    <span style={{ color: "var(--muted)" }}>Copied</span>
                  ) : null}
                </div>
                <div style={{ color: "var(--muted)", fontSize: 13 }}>
                  username: <strong>{user.username}</strong> | password:{" "}
                  <strong>{user.password}</strong>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => applyAccount(user.role, user.username, user.password)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: "1px solid var(--border-strong)",
                      background: "transparent",
                      cursor: "pointer",
                    }}
                  >
                    Use account
                  </button>
                  <button
                    type="button"
                    onClick={() => void copyAccount(user.role, user.username, user.password)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                      background: "transparent",
                      color: "var(--muted)",
                      cursor: "pointer",
                    }}
                  >
                    Copy
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p style={{ marginTop: 16, marginBottom: 0 }}>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "underline" }}>
            Back to home
          </Link>
        </p>
      </section>
    </main>
  );
};

export default LoginPage;
