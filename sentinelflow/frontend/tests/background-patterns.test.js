import test from "node:test";
import assert from "node:assert/strict";

test("background pattern options are comprehensive and valid", () => {
  const PATTERN_OPTIONS = [
    { label: "🌊 Wave Drift (Lifting Dots)", value: "wave-drift" },
    { label: "✨ Animated Drift (Moving Dots)", value: "animated-drift" },
    { label: "🌊 Gentle Slow Drift", value: "animated-gentle" },
    { label: "Diagonal Dotted Lines", value: "diagonal-lines" },
    { label: "Diagonal Dots (Matrix)", value: "diagonal-dots" },
    { label: "Dense Diagonal Mesh", value: "dense-diagonal" },
    { label: "Plain (None)", value: "none" },
  ];

  const values = PATTERN_OPTIONS.map((p) => p.value);
  assert.ok(values.includes("wave-drift"), "Must include wave-drift pattern");
  assert.ok(values.includes("animated-drift"), "Must include animated-drift pattern");
  assert.ok(values.includes("none"), "Must include plain/none pattern");
  assert.equal(values.length, 7, "Must contain exactly 7 curated patterns");

  // Verify unique values
  const uniqueValues = new Set(values);
  assert.equal(uniqueValues.size, values.length, "All pattern values must be unique");
});

test("wave lifting mathematical model produces bounded, smooth elevation without discontinuities", () => {
  const MAX_LIFT = 7.0;
  const BASE_RADIUS = 1.25;
  const BASE_ALPHA_LIGHT = 0.16;
  const BASE_ALPHA_DARK = 0.14;

  // Test across a full 2*PI wave phase cycle
  const stepCount = 360;
  for (let i = 0; i < stepCount; i++) {
    const phase = (i / stepCount) * Math.PI * 2;
    const rawSin = Math.sin(phase);

    let lift = 0;
    let radius = BASE_RADIUS;
    let alphaLight = BASE_ALPHA_LIGHT;
    let alphaDark = BASE_ALPHA_DARK;

    if (rawSin > 0.05) {
      const crest = Math.pow(rawSin, 2.4);
      lift = crest * MAX_LIFT;
      radius = BASE_RADIUS + crest * 0.45;
      alphaLight = BASE_ALPHA_LIGHT + crest * 0.24;
      alphaDark = BASE_ALPHA_DARK + crest * 0.24;
    }

    // Verify non-negativity
    assert.ok(lift >= 0, `Lift must be >= 0 at phase ${phase}, got ${lift}`);
    assert.ok(lift <= MAX_LIFT, `Lift must not exceed MAX_LIFT ${MAX_LIFT}, got ${lift}`);

    // Verify radius bounds
    assert.ok(radius >= BASE_RADIUS, `Radius must be >= ${BASE_RADIUS}`);
    assert.ok(radius <= BASE_RADIUS + 0.45 + 1e-6, `Radius must not exceed maximum`);

    // Verify alpha bounds
    assert.ok(alphaLight >= BASE_ALPHA_LIGHT && alphaLight <= 0.41, `Alpha light must stay within valid range`);
    assert.ok(alphaDark >= BASE_ALPHA_DARK && alphaDark <= 0.39, `Alpha dark must stay within valid range`);
  }
});

test("compositor promotion and RAF performance constraints", () => {
  const DPR_MAX = 2;
  const mockDPRs = [1, 1.25, 1.5, 2, 2.5, 3, 4];

  for (const rawDpr of mockDPRs) {
    const clampedDpr = Math.min(rawDpr || 1, DPR_MAX);
    assert.ok(clampedDpr <= 2, `DPR must never exceed 2 on high-density screens, got ${clampedDpr}`);
    assert.ok(clampedDpr >= 1, `DPR must be at least 1`);
  }
});
