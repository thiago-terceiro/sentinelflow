import type { Metadata } from "next";
import { IBM_Plex_Mono, Nunito, Space_Grotesk } from "next/font/google";
import { cookies } from "next/headers";
import Link from "next/link";

import { NavbarLinks } from "@/components/NavbarLinks";
import { StructuredData } from "@/components/StructuredData";
import { StyleSwitcher } from "@/components/StyleSwitcher";
import { ACCESS_TOKEN_COOKIE_NAME, TEST_USER_COOKIE_NAME } from "@/lib/testAuth";

import "./globals.css";

const headline = Space_Grotesk({ subsets: ["latin"], variable: "--font-headline" });
const body = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600"],
});
const rounded = Nunito({
  subsets: ["latin"],
  variable: "--font-rounded",
  weight: ["400", "500", "600", "700", "800"],
});

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
    <html
      lang="en"
      data-style="style-2"
      className={`${headline.variable} ${body.variable} ${rounded.variable}`}
    >
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;600;700&family=DM+Sans:wght@400;500;700&family=Inter:wght@400;500;600;700&family=Lexend:wght@400;500;600&family=Nunito:wght@400;600;700;800&family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Poppins:wght@400;500;600;700&family=Quicksand:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
        <StructuredData />
      </head>
      <body>
        <header className="app-header">
          <div className="app-header-inner">
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
                <span className="nav-icon">⚡ </span>SentinelFlow
              </Link>

              <NavbarLinks hasSession={hasSession} userRole={role ?? null} />
            </div>


            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <StyleSwitcher />
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
                  className="nav-signin-btn"
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
