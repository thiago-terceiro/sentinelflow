"use client";

import { useEffect, useState } from "react";

interface BgPreset {
  label: string;
  value: string;
}

interface FontOption {
  label: string;
  fontFamily: string;
}

const THEME_STORAGE_KEY = "sentinelflow_theme";
const BG_STORAGE_KEY = "sentinelflow_style2_bg";
const FONT_STORAGE_KEY = "sentinelflow_style2_font";

// User requested defaults: font 4 Plus Jakarta Sans and bg color soft slate (#f1f5f9)
const DEFAULT_STYLE2_BG = "#f1f5f9";
const DEFAULT_STYLE2_FONT = "4. Plus Jakarta Sans";

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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    let savedTheme: string | null = null;
    let savedBg: string | null = null;
    let savedFont: string | null = null;
    try {
      savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
      savedBg = localStorage.getItem(BG_STORAGE_KEY);
      savedFont = localStorage.getItem(FONT_STORAGE_KEY);
    } catch {
      savedTheme = null;
      savedBg = null;
      savedFont = null;
    }

    const initialTheme = savedTheme === "dark" ? "dark" : "light";
    const initialBg = savedBg ?? (initialTheme === "dark" ? "#0f172a" : DEFAULT_STYLE2_BG);
    const initialFont = savedFont ?? DEFAULT_STYLE2_FONT;

    setCurrentTheme(initialTheme);
    setCurrentBg(initialBg);
    setCurrentFont(initialFont);

    document.documentElement.setAttribute("data-style", "style-2");
    document.documentElement.setAttribute("data-theme", initialTheme);
    document.documentElement.style.setProperty("--style2-bg", initialBg);

    const matched = FONT_OPTIONS.find((f) => f.label.includes(initialFont)) ?? FONT_OPTIONS[3];
    document.documentElement.style.setProperty("--font-active", matched.fontFamily);

    setMounted(true);
  }, []);

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
    <div
      role="group"
      aria-label="Theme and Typography Controls"
      className="style-controls-group"
    >
      {/* Theme Switcher before Font Dropdown */}
      <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <label htmlFor="theme-select" style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)" }}>
          Theme:
        </label>
        <select
          id="theme-select"
          value={currentTheme}
          onChange={(e) => handleSelectTheme(e.target.value as "light" | "dark")}
          className="font-picker-select"
          aria-label="Select theme mode"
          title="Select theme mode (Light or Dark)"
        >
          <option value="light">☀️ Light</option>
          <option value="dark">🌙 Dark</option>
        </select>
      </div>

      {/* 10-Font Dropdown Selector */}
      <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <label htmlFor="font-select" style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)" }}>
          Font:
        </label>
        <select
          id="font-select"
          value={currentFont}
          onChange={(e) => handleSelectFont(e.target.value)}
          className="font-picker-select"
          aria-label="Select typography font"
          title="Select one of 10 fonts to preview"
        >
          {FONT_OPTIONS.map((f) => (
            <option key={f.label} value={f.label}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      {/* Simple Background Color Palette Control */}
      <div
        role="radiogroup"
        aria-label="Background Color Palette"
        className="bg-palette-toolbar"
      >
        <span className="bg-palette-label">BG:</span>
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

        {/* Custom Color Input Swatch */}
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
  );
};
