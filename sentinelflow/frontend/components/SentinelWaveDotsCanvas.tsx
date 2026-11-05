"use client";

import React, { useEffect, useRef } from "react";

const GRID_SPACING = 38;
const BASE_RADIUS = 1.25;
const MAX_LIFT = 7.0;
const WAVE_SPEED = 0.0016;
const WAVE_FREQUENCY = 0.014;

export const SentinelWaveDotsCanvas = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) {
      return;
    }

    let rafId: number | null = null;
    let isRunning = false;
    let width = 0;
    let height = 0;
    let dpr = 1;
    let isDarkMode = false;
    let isWaveActive = false;

    // Check reduced motion preference
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const checkState = () => {
      const pattern = document.documentElement.getAttribute("data-pattern") ?? "wave-drift";
      const theme = document.documentElement.getAttribute("data-theme") ?? "light";
      isWaveActive = pattern === "wave-drift";
      isDarkMode = theme === "dark";
      canvas.style.display = isWaveActive ? "block" : "none";
    };

    const handleResize = () => {
      try {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = window.innerWidth;
        height = window.innerHeight;

        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);

        if (!isRunning && isWaveActive) {
          drawFrame(performance.now());
        }
      } catch (err) {
        console.error("Canvas resize error:", err);
      }
    };

    const drawFrame = (timestamp: number) => {
      if (!isWaveActive) {
        return;
      }

      ctx.clearRect(0, 0, width, height);

      const baseR = isDarkMode ? 241 : 30;
      const baseG = isDarkMode ? 245 : 41;
      const baseB = isDarkMode ? 249 : 59;
      const baseAlpha = isDarkMode ? 0.14 : 0.16;

      const time = prefersReducedMotion ? 0 : timestamp;
      const phaseOffset = time * WAVE_SPEED;

      const cols = Math.ceil(width / GRID_SPACING) + 2;
      const rows = Math.ceil(height / GRID_SPACING) + 2;

      // Single beginPath pass for resting dots to maximize compositor performance
      ctx.beginPath();
      ctx.fillStyle = `rgba(${baseR}, ${baseG}, ${baseB}, ${baseAlpha})`;

      // Second list for lifted wave dots to render with elevated alpha & lift
      const liftedDots: { x: number; y: number; r: number; a: number }[] = [];

      for (let row = 0; row < rows; row++) {
        // Diagonal stagger offset: alternate rows shift by half spacing
        const xOffset = (row % 2) * (GRID_SPACING / 2);

        for (let col = 0; col < cols; col++) {
          const x = col * GRID_SPACING + xOffset;
          const y = row * GRID_SPACING;

          // Wave propagation along 45-degree diagonal: d = (x + y) * 0.7071
          const diag = (x + y) * 0.7071;
          const phase = diag * WAVE_FREQUENCY - phaseOffset;
          const rawSin = Math.sin(phase);

          if (rawSin > 0.05 && !prefersReducedMotion) {
            // Dot is in the positive wave crest - calculate lift, radius expansion, and illumination
            const crest = Math.pow(rawSin, 2.4);
            const lift = crest * MAX_LIFT;
            const radius = BASE_RADIUS + crest * 0.45;
            const alpha = baseAlpha + crest * 0.24;

            liftedDots.push({
              x: x - lift * 0.35,
              y: y - lift,
              r: radius,
              a: alpha,
            });
          } else {
            // Resting grid dot
            ctx.moveTo(x + BASE_RADIUS, y);
            ctx.arc(x, y, BASE_RADIUS, 0, Math.PI * 2);
          }
        }
      }

      // Draw all resting dots in a single GPU draw call
      ctx.fill();

      // Draw lifted dots
      for (let i = 0; i < liftedDots.length; i++) {
        const dot = liftedDots[i];
        ctx.beginPath();
        ctx.fillStyle = `rgba(${baseR}, ${baseG}, ${baseB}, ${dot.a.toFixed(3)})`;
        ctx.arc(dot.x, dot.y, dot.r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const renderLoop = (timestamp: number) => {
      if (!isWaveActive || document.hidden || prefersReducedMotion) {
        isRunning = false;
        return;
      }

      drawFrame(timestamp);
      rafId = requestAnimationFrame(renderLoop);
    };

    const startAnimation = () => {
      checkState();
      if (isWaveActive && !document.hidden && !prefersReducedMotion) {
        if (!isRunning) {
          isRunning = true;
          rafId = requestAnimationFrame(renderLoop);
        }
      } else {
        isRunning = false;
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        if (isWaveActive) {
          drawFrame(performance.now());
        }
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        isRunning = false;
      } else {
        startAnimation();
      }
    };

    // Observe documentElement attribute changes for data-pattern and data-theme
    const observer = new MutationObserver(() => {
      startAnimation();
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-pattern", "data-theme"],
    });

    document.addEventListener("visibilitychange", handleVisibility, { passive: true });
    window.addEventListener("resize", handleResize, { passive: true });

    checkState();
    handleResize();
    startAnimation();

    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("resize", handleResize);
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      data-testid="sentinel-wave-canvas"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: -1,
        willChange: "transform",
        transform: "translateZ(0)",
      }}
    />
  );
};
