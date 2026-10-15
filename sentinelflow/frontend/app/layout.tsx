import type { Metadata } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import { cookies } from "next/headers";
import Link from "next/link";

import { ACCESS_TOKEN_COOKIE_NAME, TEST_USER_COOKIE_NAME } from "@/lib/testAuth";

import "./globals.css";

const headline = Space_Grotesk({ subsets: ["latin"], variable: "--font-headline" });
const body = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
    title: "SentinelFlow",
    description: "AI dispute investigation console and audit log system",
};

const RootLayout = async ({ children }: Readonly<{ children: React.ReactNode }>) => {
    const cookieStore = await cookies();
    const hasSession = Boolean(cookieStore.get(ACCESS_TOKEN_COOKIE_NAME)?.value);
    const userInfo = cookieStore.get(TEST_USER_COOKIE_NAME)?.value ?? "";
    const [username, role] = userInfo.split(":", 2);
    const sessionLabel = username && role ? `${username} (${role})` : null;

    return (
        <html lang="en" className={`${headline.variable} ${body.variable}`}>
            <body>
                <header style={{ width: "min(1150px, calc(100vw - 2rem))", margin: "24px auto 0" }}>
                    <div
                        className="shell-card"
                        style={{
                            padding: "14px 20px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                        }}
                    >
                        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                            <Link
                                href="/"
                                style={{
                                    fontWeight: 700,
                                    fontSize: 16,
                                    textDecoration: "none",
                                    color: "var(--foreground)",
                                    letterSpacing: "-0.02em",
                                }}
                            >
                                ⚡ SentinelFlow
                            </Link>

                            <nav style={{ display: "flex", gap: 14, fontSize: 13 }}>
                                <Link
                                    href="/"
                                    style={{
                                        color: "var(--muted)",
                                        textDecoration: "none",
                                        fontWeight: 500,
                                    }}
                                >
                                    Disputes
                                </Link>
                                <Link
                                    href="/audit"
                                    style={{
                                        color: "var(--accent)",
                                        textDecoration: "none",
                                        fontWeight: 600,
                                    }}
                                >
                                    🛡️ Auditor Portal
                                </Link>
                            </nav>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                            {hasSession && sessionLabel ? (
                                <span
                                    style={{
                                        fontSize: 12,
                                        padding: "3px 8px",
                                        borderRadius: 999,
                                        background: "rgba(255,255,255,0.06)",
                                        color: "var(--foreground)",
                                    }}
                                >
                                    {sessionLabel}
                                </span>
                            ) : null}
                            {hasSession ? (
                                <Link
                                    href="/auth/logout"
                                    prefetch={false}
                                    style={{ color: "var(--muted)", fontSize: 13, textDecoration: "none" }}
                                >
                                    Sign out
                                </Link>
                            ) : (
                                <Link
                                    href="/login"
                                    style={{ color: "var(--accent)", fontSize: 13, textDecoration: "none", fontWeight: 600 }}
                                >
                                    Sign in
                                </Link>
                            )}
                        </div>
                    </div>
                </header>
                {children}
            </body>
        </html>
    );
};

export default RootLayout;
