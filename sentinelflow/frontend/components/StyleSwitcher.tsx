"use client";

import { useEffect, useRef, useState } from "react";

interface BgPreset {
  label: string;
  value: string;
}

interface FontOption {
  label: string;
  fontFamily: string;
}

interface PatternOption {
  label: string;
  value: string;
}

const THEME_STORAGE_KEY = "sentinelflow_theme";
const BG_STORAGE_KEY = "sentinelflow_style2_bg";
const FONT_STORAGE_KEY = "sentinelflow_style2_font";
const PATTERN_STORAGE_KEY = "sentinelflow_style2_pattern";

// User requested defaults: font 4 Plus Jakarta Sans and bg color soft slate (#f1f5f9)
const DEFAULT_STYLE2_BG = "#f1f5f9";
const DEFAULT_STYLE2_FONT = "4. Plus Jakarta Sans";
const DEFAULT_STYLE2_PATTERN = "wave-drift";

const PATTERN_OPTIONS: PatternOption[] = [
  { label: "🌊 Wave Drift (Lifting Dots)", value: "wave-drift" },
  { label: "✨ Animated Drift (Moving Dots)", value: "animated-drift" },
  { label: "🌊 Gentle Slow Drift", value: "animated-gentle" },
  { label: "Diagonal Dotted Lines", value: "diagonal-lines" },
  { label: "Diagonal Dots (Matrix)", value: "diagonal-dots" },
  { label: "Dense Diagonal Mesh", value: "dense-diagonal" },
  { label: "Plain (None)", value: "none" },
];

const FONT_OPTIONS: FontOption[] = [
  { label: "1. Nunito (Rounded)", fontFamily: "'Nunito', sans-serif" },
  { label: "2. Quicksand (Soft)", fontFamily: "'Quicksand', sans-serif" },
  { label: "3. Comfortaa (Ultra Rounded)", fontFamily: "'Comfortaa', cursive, sans-serif" },
  { label: "4. Plus Jakarta Sans", fontFamily: "'Plus Jakarta Sans', sans-serif" },
  { label: "5. Outfit (Curved)", fontFamily: "'Outfit', sans-serif" },
  { label: "6. Lexend (Readable)", fontFamily: "'Lexend', sans-serif" },
  { label: "7. Inter (Neo-Grotesque)", fontFamily: "'Inter', sans-serif" },
  { label: "8. Poppins (Geometric)", fontFamily: "'Poppins', sans-serif" },
  { label: "9. DM Sans (Contemporary)", fontFamily: "'DM Sans', sans-serif" },
  { label: "10. Space Grotesk (Tech)", fontFamily: "'Space Grotesk', sans-serif" },
];

const BG_PRESETS: BgPreset[] = [
  { label: "Pure White", value: "#ffffff" },
  { label: "Soft Slate", value: "#f1f5f9" },
  { label: "Warm Sand", value: "#faf8f5" },
  { label: "Cool Mint", value: "#f0fdf4" },
  { label: "Ice Sky", value: "#f0f9ff" },
  { label: "Soft Zinc", value: "#f4f4f5" },
  { label: "Dark Slate", value: "#0f172a" },
];

export const StyleSwitcher = () => {
  const [currentTheme, setCurrentTheme] = useState<"light" | "dark">("light");
  const [currentBg, setCurrentBg] = useState<string>(DEFAULT_STYLE2_BG);
  const [currentFont, setCurrentFont] = useState<string>(DEFAULT_STYLE2_FONT);
  const [currentPattern, setCurrentPattern] = useState<string>(DEFAULT_STYLE2_PATTERN);
  const [isOpen, setIsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let savedTheme: string | null = null;
    let savedBg: string | null = null;
    let savedFont: string | null = null;
    let savedPattern: string | null = null;
    try {
      savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
      savedBg = localStorage.getItem(BG_STORAGE_KEY);
      savedFont = localStorage.getItem(FONT_STORAGE_KEY);
      savedPattern = localStorage.getItem(PATTERN_STORAGE_KEY);
    } catch {
      savedTheme = null;
      savedBg = null;
      savedFont = null;
      savedPattern = null;
    }

    const initialTheme = savedTheme === "dark" ? "dark" : "light";
    const initialBg = savedBg ?? (initialTheme === "dark" ? "#0f172a" : DEFAULT_STYLE2_BG);
    const initialFont = savedFont ?? DEFAULT_STYLE2_FONT;
    const initialPattern = savedPattern ?? DEFAULT_STYLE2_PATTERN;

    setCurrentTheme(initialTheme);
    setCurrentBg(initialBg);
    setCurrentFont(initialFont);
    setCurrentPattern(initialPattern);

    document.documentElement.setAttribute("data-style", "style-2");
    document.documentElement.setAttribute("data-theme", initialTheme);
    document.documentElement.setAttribute("data-pattern", initialPattern);
    document.documentElement.style.setProperty("--style2-bg", initialBg);

    const matched = FONT_OPTIONS.find((f) => f.label.includes(initialFont)) ?? FONT_OPTIONS[3];
    document.documentElement.style.setProperty("--font-active", matched.fontFamily);

    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        triggerButtonRef.current?.focus();
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleSelectTheme = (theme: "light" | "dark") => {
    setCurrentTheme(theme);
    document.documentElement.setAttribute("data-theme", theme);
    if (theme === "dark" && currentBg !== "#0f172a") {
      handleSelectBg("#0f172a");
    } else if (theme === "light" && currentBg === "#0f172a") {
      handleSelectBg(DEFAULT_STYLE2_BG);
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // LocalStorage access may be restricted
    }
  };

  const handleSelectPattern = (pattern: string) => {
    setCurrentPattern(pattern);
    document.documentElement.setAttribute("data-pattern", pattern);
    try {
      localStorage.setItem(PATTERN_STORAGE_KEY, pattern);
    } catch {
      // LocalStorage access may be restricted
    }
  };

  const handleSelectBg = (color: string) => {
    setCurrentBg(color);
    document.documentElement.style.setProperty("--style2-bg", color);
    try {
      localStorage.setItem(BG_STORAGE_KEY, color);
    } catch {
      // LocalStorage access may be restricted
    }
  };

  const handleSelectFont = (fontLabel: string) => {
    setCurrentFont(fontLabel);
    const matched = FONT_OPTIONS.find((f) => f.label === fontLabel) ?? FONT_OPTIONS[3];
    document.documentElement.style.setProperty("--font-active", matched.fontFamily);
    try {
      localStorage.setItem(FONT_STORAGE_KEY, fontLabel);
    } catch {
      // LocalStorage access may be restricted
    }
  };

  if (!mounted) {
    return null;
  }

  return (
    <div style={{ position: "relative" }} ref={containerRef}>
      {/* Tidy Navbar Trigger Button */}
      <button
        ref={triggerButtonRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-controls="accessibility-appearance-menu"
        aria-label="Appearance and accessibility preferences"
        title="Appearance & accessibility preferences (Theme, Font, Background)"
        style={{
          minWidth: 44,
          minHeight: 44,
          width: 44,
          height: 44,
          padding: 0,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          border: "1px solid var(--panel-border)",
          background: isOpen ? "var(--accent-soft, #dbeafe)" : "transparent",
          color: isOpen ? "var(--accent, #1e3a8a)" : "var(--foreground)",
          cursor: "pointer",
          fontSize: 18,
          transition: "background 0.15s ease, border-color 0.15s ease",
        }}
        className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      >
        <span aria-hidden="true">🎨</span>
      </button>

      {/* Mobile Backdrop */}
      {isOpen ? (
        <div
          className="appearance-menu-backdrop"
          onClick={() => {
            setIsOpen(false);
            triggerButtonRef.current?.focus();
          }}
          aria-hidden="true"
        />
      ) : null}

      {/* Tidy Appearance Dropdown Menu */}
      {isOpen ? (
        <div
          id="accessibility-appearance-menu"
          role="dialog"
          aria-label="Appearance and accessibility preferences"
          className="appearance-menu-popover"
        >
          {/* Header with Title and Close Button */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              paddingBottom: 10,
              borderBottom: "1px solid var(--panel-border)",
            }}
          >
            <div>
              <strong style={{ fontSize: 13, color: "var(--foreground)", display: "block" }}>
                Appearance Preferences
              </strong>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>
                Theme, typography &amp; background
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                triggerButtonRef.current?.focus();
              }}
              aria-label="Close preferences menu"
              style={{
                minWidth: 44,
                minHeight: 44,
                background: "transparent",
                border: "none",
                color: "var(--foreground)",
                fontSize: 16,
                fontWeight: 700,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 6,
              }}
              className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            >
              ✕
            </button>
          </div>

          {/* Theme Mode Selector */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label
              htmlFor="theme-select"
              style={{ fontSize: 12, fontWeight: 700, color: "var(--foreground)" }}
            >
              Theme Mode:
            </label>
            <select
              id="theme-select"
              value={currentTheme}
              onChange={(e) => handleSelectTheme(e.target.value as "light" | "dark")}
              className="font-picker-select"
              style={{ minHeight: 44, height: 44, width: "100%", borderRadius: 6 }}
            >
              <option value="light">☀️ Light Mode</option>
              <option value="dark">🌙 Dark Mode</option>
            </select>
          </div>

          {/* Typography Font Selector */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label
              htmlFor="font-select"
              style={{ fontSize: 12, fontWeight: 700, color: "var(--foreground)" }}
            >
              Typography Font:
            </label>
            <select
              id="font-select"
              value={currentFont}
              onChange={(e) => handleSelectFont(e.target.value)}
              className="font-picker-select"
              style={{ minHeight: 44, height: 44, width: "100%", borderRadius: 6 }}
            >
              {FONT_OPTIONS.map((f) => (
                <option key={f.label} value={f.label}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          {/* Background Canvas Palette */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span
              id="bg-palette-heading"
              style={{ fontSize: 12, fontWeight: 700, color: "var(--foreground)" }}
            >
              Background Canvas:
            </span>
            <div
              role="radiogroup"
              aria-labelledby="bg-palette-heading"
              style={{ display: "flex", flexWrap: "wrap", gap: 6 }}
            >
              {BG_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  role="radio"
                  aria-checked={currentBg.toLowerCase() === preset.value.toLowerCase()}
                  aria-label={`Set background color to ${preset.label}`}
                  title={`${preset.label} (${preset.value})`}
                  onClick={() => handleSelectBg(preset.value)}
                  className={`bg-palette-swatch ${
                    currentBg.toLowerCase() === preset.value.toLowerCase() ? "is-active" : ""
                  }`}
                  style={{ backgroundColor: preset.value }}
                />
              ))}

              <label
                title="Custom background color"
                className="bg-palette-picker-btn"
                aria-label="Pick custom background color"
              >
                <span aria-hidden="true">🎨</span>
                <input
                  type="color"
                  value={currentBg}
                  onChange={(e) => handleSelectBg(e.target.value)}
                  className="bg-palette-picker-input"
                  aria-label="Custom background color picker"
                />
              </label>
            </div>
          </div>

          {/* Background Pattern Selector */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label
              htmlFor="pattern-select"
              style={{ fontSize: 12, fontWeight: 700, color: "var(--foreground)" }}
            >
              Background Pattern:
            </label>
            <select
              id="pattern-select"
              value={currentPattern}
              onChange={(e) => handleSelectPattern(e.target.value)}
              className="font-picker-select"
              style={{ minHeight: 44, height: 44, width: "100%", borderRadius: 6 }}
            >
              {PATTERN_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : null}
    </div>
  );
};
