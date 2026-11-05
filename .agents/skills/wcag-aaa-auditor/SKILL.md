---
name: wcag-aaa-auditor
description: >-
  Audits, verifies, and enforces WCAG 2.1 and 2.2 Level AAA accessibility standards,
  minimum 44x44px touch targets, >=7:1 color contrast, WCAG 2.5.3 Label in Name compliance,
  keyboard navigation, and WAI-ARIA role semantics across web applications.
  Use whenever creating or modifying UI components, pages, forms, or interactive controls,
  or when auditing and fixing accessibility issues.
---

# WCAG AAA Accessibility Auditor Skill

This skill provides an exhaustive, non-negotiable runbook for designing, auditing, and enforcing **WCAG 2.1 & 2.2 Level AAA** compliance, zero-violation Axe-Core audits, and dev-time automated gate enforcement across all frontend interfaces.

---

## 1. Non-Negotiable WCAG AAA Mandates

Every interactive control, typography token, and layout container MUST satisfy the following criteria:

### A. Touch Target Sizing (WCAG 2.5.5 Level AAA & Global UI Rule 2.3)
- **Minimum 44×44 CSS Pixels:** Every clickable button, anchor link, input control, tab, switch, swatch, and interactive element MUST have a target bounding box of at least **44×44px**.
- **Compact UI Handling (Zero Visual Distortion):** If visual aesthetics require a compact glyph or swatch (e.g. 18px–24px), use CSS pseudo-elements (`::after` or `::before`) with `position: absolute; min-width: 44px; min-height: 44px; top: 50%; left: 50%; transform: translate(-50%, -50%);` to guarantee the physical hit target is 44×44px without breaking visual layout.
- **Button Padding Standards:** Standard interactive buttons should use at minimum `padding: 10px 16px; min-height: 44px;` or `min-height: 48px;`.

### B. Color Contrast Ratios (WCAG 1.4.6 Level AAA & WCAG 1.4.11 Level AA)
- **Normal Text (< 18pt / 24px normal, or < 14pt / 18.66px bold):** Minimum **7.0:1** contrast ratio against its background.
- **Large Text (≥ 18pt / 24px normal, or ≥ 14pt / 18.66px bold):** Minimum **4.5:1** contrast ratio against its background.
- **UI Components & Graphical States (WCAG 1.4.11):** Minimum **3.0:1** contrast ratio for borders, active indicator rings, icons, and focus outlines.
- **Recommended Palette for White/Light Gray (#ffffff / #f1f5f9) Backgrounds:**
  - Dark Navy / Ink: `#0f172a` (15:1 ratio)
  - Muted Text: `#334155` (8.3:1 ratio on #f1f5f9, 9.5:1 on #ffffff)
  - Success Text: `#14532d` (8.4:1 ratio on #ffffff, 7.1:1 on #dcfce7)
  - Error Text: `#991b1b` (7.7:1 ratio on #ffffff, 7.1:1 on #fee2e2)
  - Warning Text: `#78350f` (8.5:1 ratio on #ffffff, 7.2:1 on #fef3c7)
  - Primary Accent Text: `#1e3a8a` (10.5:1 ratio on #ffffff, 8.2:1 on #dbeafe)

### C. WCAG 2.5.3 "Label in Name" (Level A)
- **Speech Input & Screen Reader Parity:** The accessible name (`aria-label` or inner text) MUST contain the exact text presented visually on the component.
- **Example Violation:** Button displays `"Reset"`, but carries `aria-label="Clear all buffered messages"`. Speech users saying *"Click Reset"* fail.
- **Correct Pattern:** `aria-label="Reset telemetry and clear all buffered messages"`. The visual label `"Reset"` appears at the start of the accessible name.

### D. Accessible Disambiguation (WCAG 4.1.2 & WCAG 2.4.6)
- **Zero Ambiguous Repeated Buttons:** When multiple buttons share identical visual text (e.g. `"Escalate"`, `"Edit"`, `"Delete"` across list rows), every button MUST include a distinct, contextual accessible name:
  ```tsx
  <button
    type="button"
    aria-label={`Escalate ${item.carrier} alert for ${item.sender} to SentinelFlow`}
  >
    <span>⚡</span>
    <span>Escalate to SentinelFlow</span>
  </button>
  ```

### E. WAI-ARIA Role & Structure Integrity
- **Tab Pattern Integrity:** Never use `role="tab"` or `role="tablist"` unless paired with `role="tabpanel"`, controlled via `aria-controls`, and equipped with arrow-key roving tabindex navigation.
- **Filter Pills:** For streaming feeds, tables, or item filters, use a group of toggle buttons:
  ```tsx
  <div role="group" aria-label="Filter events by verdict">
    {options.map((opt) => (
      <button
        type="button"
        key={opt}
        aria-pressed={selected === opt}
        aria-label={`Filter events by ${opt} verdict`}
        onClick={() => setSelected(opt)}
      >
        {opt}
      </button>
    ))}
  </div>
  ```
- **Scenario Presets:** Template and preset buttons that populate input fields are action buttons, NOT tabs. Use `type="button"` with `aria-label="Load preset scenario: <Name>"`.

### F. Keyboard Focus Rings (WCAG 2.4.7 AA & 2.4.13 AAA)
- Every interactive element MUST have an unmistakable `:focus-visible` ring.
- High contrast focus ring standard:
  ```css
  button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible {
    outline: 2px solid var(--accent, #1e40af);
    outline-offset: 2px;
  }
  ```

---

## 2. Dev-Time Automated Verification Procedure

Whenever any UI code is created or modified, execute the automated accessibility verification suite:

1. **Run Dev-Time A11y Suite:**
   ```bash
   pnpm test:a11y
   # or: node scripts/test-a11y-aaa.mjs
   ```
2. **Automated Suite Checks:**
   - Evaluates headless Chromium pages against Axe-Core with tags `["wcag2aaa", "wcag21aaa", "wcag22aaa", "best-practice"]`.
   - Inspects all DOM buttons and interactive controls for physical dimensions (`width >= 44 && height >= 44`).
   - Asserts zero duplicate un-contextualized accessible names.
   - Asserts WCAG 2.5.3 Label in Name compliance.
3. **Exit Code Policy:**
   - Exit code 0: 100% WCAG AAA compliant.
   - Exit code > 0: Fails the gate. Report exact component, file, line number, and violation details.
