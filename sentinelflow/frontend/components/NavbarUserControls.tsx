"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { NavSignInButton } from "@/components/NavSignInButton";
import { useSentinelPulse } from "@/components/SentinelPulseProvider";

type Props = {
  initialHasSession: boolean;
  initialSessionLabel: string | null;
};

export const NavbarUserControls = ({ initialHasSession, initialSessionLabel }: Props) => {
  const pathname = usePathname();
  const { hasSession, username, isResetting, clearSession, resetAllToDefaults } =
    useSentinelPulse();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const hideResetButton = pathname === "/" || pathname === "/disputes" || pathname === "/login";
  const effectiveHasSession = hasSession && !isSigningOut;
  const formattedUsername = username
    ? username.charAt(0).toUpperCase() + username.slice(1)
    : initialSessionLabel;

  const handleSignOut = async () => {
    if (isSigningOut) {
      return;
    }
    setIsSigningOut(true);
    clearSession();
    try {
      await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
      });
    } catch {
      // Proceed with hard redirect even if network request fails
    }
    window.location.replace("/");
  };

  const handleReset = async () => {
    if (isResetting) {
      return;
    }
    await resetAllToDefaults();
  };

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        flexShrink: 0,
        whiteSpace: "nowrap",
      }}
    >
      {!hideResetButton ? (
        <button
          type="button"
          onClick={() => void handleReset()}
          disabled={isResetting}
          aria-label="Reset all disputes and telemetry to defaults"
          title="Reset database disputes, investigations, and telemetry to default state"
          style={{
            fontSize: 13,
            minHeight: 44,
            padding: "8px 14px",
            borderRadius: 999,
            border: "1px solid var(--panel-border)",
            background: "rgba(255,255,255,0.04)",
            color: "var(--muted)",
            cursor: isResetting ? "not-allowed" : "pointer",
            fontWeight: 600,
            transition: "color 0.15s ease, border-color 0.15s ease",
          }}
          className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          {isResetting ? "Resetting..." : "↻ Reset"}
        </button>
      ) : null}

      {effectiveHasSession && formattedUsername ? (
        <span
          style={{
            fontSize: 12,
            padding: "6px 12px",
            minHeight: 44,
            display: "inline-flex",
            alignItems: "center",
            borderRadius: 999,
            background: "rgba(255,255,255,0.06)",
            color: "var(--foreground)",
          }}
        >
          {formattedUsername}
        </span>
      ) : null}

      {effectiveHasSession || (initialHasSession && hasSession && !isSigningOut) ? (
        <button
          type="button"
          onClick={() => void handleSignOut()}
          disabled={isSigningOut}
          style={{
            border: 0,
            background: "transparent",
            minHeight: 44,
            padding: "8px 12px",
            display: "inline-flex",
            alignItems: "center",
            color: "var(--muted)",
            fontSize: 13,
            fontWeight: 600,
            cursor: isSigningOut ? "not-allowed" : "pointer",
            fontFamily: "inherit",
          }}
          className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          {isSigningOut ? "Signing out..." : "Sign out"}
        </button>
      ) : (
        <NavSignInButton />
      )}
    </div>
  );
};
