import type { Metadata } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import { cookies } from "next/headers";
import Link from "next/link";

import { ACCESS_TOKEN_COOKIE_NAME } from "@/lib/oidc";

import "./globals.css";

const headline = Space_Grotesk({ subsets: ["latin"], variable: "--font-headline" });
const body = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
    title: "SentinelFlow",
    description: "AI dispute investigation console",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
    const cookieStore = await cookies();
    const hasSession = Boolean(cookieStore.get(ACCESS_TOKEN_COOKIE_NAME)?.value);

    return (
        <html lang="en" className={`${headline.variable} ${body.variable}`}>
            <body>
                <header style={{ width: "min(1150px, calc(100vw - 2rem))", margin: "24px auto 0" }}>
                    <div
                        className="shell-card"
                        style={{
                            padding: "12px 16px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                        }}
                    >
                        <strong>SentinelFlow Console</strong>
                        {hasSession ? (
                            <Link href="/auth/logout" style={{ color: "var(--muted)" }}>Sign out</Link>
                        ) : (
                            <Link href="/auth/login" style={{ color: "var(--muted)" }}>Sign in</Link>
                        )}
                    </div>
                </header>
                {children}
            </body>
        </html>
    );
}
