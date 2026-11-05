---
name: sentinelflow-animation-performance
description: >-
  Architects, profiles, and verifies ultra-low-latency 60fps/120fps web animations and background visual effects in SentinelFlow and SentinelPulse. Enforces compositor-only GPU pipelines, Canvas 2D/WebGL RAF lifecycle optimization, zero Garbage Collection thrashing in animation ticks, visibility suppression, DPR clamping, and WCAG 2.2 Level AAA reduced-motion accessibility.
---

# SentinelFlow Animation Performance & Compositor Optimization Skill

This skill provides architectural rules, optimization procedures, and verification protocols for building zero-lag, 60fps/120fps animations and background effects in SentinelFlow.

---

## 1. Frame Budgets & Latency Targets

Every animation frame operates within strict hardware refresh budgets:

```
60Hz Standard Display Budget:  16.66 ms
├── JS Tick (RAF Execution):    < 1.50 ms
├── Style & Layout:             0.00 ms (Strictly Composite-Only)
├── Paint & Raster:             0.00 ms (No CPU Paint Invalidation)
└── GPU Compositing:            < 2.50 ms
Headroom:                      > 12.60 ms

120Hz ProMotion / High-Refresh Budget: 8.33 ms
├── JS Tick (RAF Execution):    < 1.00 ms
├── GPU Compositing:            < 1.50 ms
Headroom:                      > 5.80 ms
```

---

## 2. The Four Cardinal Rules of Web Animation Performance

### Rule 1: Composite-Only Properties
Never animate properties that trigger Layout or Paint in continuous loops:
- **Allowed (Composite-Only)**: `transform` (`translate3d`, `scale3d`, `rotate3d`), `opacity`.
- **Prohibited in Continuous Animation**: `background-position`, `top`, `left`, `right`, `bottom`, `width`, `height`, `margin`, `padding`, `box-shadow`, `filter: blur()`.
- **Compositor Promotion**: Promote animated containers into dedicated GPU layers using:
  ```css
  will-change: transform;
  transform: translateZ(0);
  contain: strict;
  ```

### Rule 2: Zero Allocations in the Render Tick
Garbage Collection (GC) pauses are the #1 cause of micro-stutter (jank).
- **Zero In-Tick Allocation**: Never allocate objects (`{}`), arrays (`[]`), closures, or strings inside `requestAnimationFrame(tick)`.
- Pre-allocate all buffers, vectors, math caches, and color strings outside the loop:
  ```ts
  // GOOD: Pre-allocated buffer and primitive reuse
  const state = { x: 0, y: 0, lift: 0, radius: 0, alpha: 0 };
  
  // BAD: Creating objects inside tick
  const update = () => dots.map(d => ({ ...d, y: d.y + 1 }));
  ```

### Rule 3: Strict RAF Lifecycle & Tab Visibility Suspension
Animations running in background tabs waste mobile battery, drain CPU/GPU, and cause memory thrashing.
- **Visibility Suspension**:
  ```ts
  const handleVisibility = () => {
    if (document.hidden) {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = null;
    } else {
      lastTime = performance.now();
      rafId = requestAnimationFrame(render);
    }
  };
  document.addEventListener('visibilitychange', handleVisibility);
  ```
- **Time-Delta Clamping**: Always clamp `deltaTime` (e.g. `Math.min(now - lastTime, 64)`) to prevent giant physics jumps when waking from sleep or background tabs.

### Rule 4: Canvas DPR Clamping & Batching
- **Device Pixel Ratio (DPR) Clamping**:
  ```ts
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  ctx.scale(dpr, dpr);
  ```
  *Never allocate 3x or 4x canvases on high-DPI screens without clamping; it exhausts mobile VRAM and GPU fill rate.*
- **Batch Path Drawing**: Group identical primitives into a single `beginPath()` and `fill()` call rather than individual paths per element.

---

## 3. WCAG 2.2 Level AAA Accessibility Mandates

1. **Reduced Motion**:
   ```ts
   const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
   if (prefersReducedMotion) {
     drawStaticTranquilFrame();
     return; // Never start requestAnimationFrame loop
   }
   ```
2. **Sensory Safety**: No flashing, blinking, or alternating luminance exceeding 3Hz. Wave displacements must remain subtle ($\le 8\text{px}$) and continuous.

---

## 4. Verification & Profiling Checklist

Before approving any animation change:
- [ ] **Frame Time**: Profiler shows JS execution time $< 1.5\text{ ms}$ per tick.
- [ ] **Paint Flashing**: Chrome DevTools *Rendering > Paint Flashing* shows green boxes only on load, ZERO continuous flashing during loop.
- [ ] **Layer Borders**: Animated element has its own GPU composite layer (orange borders in DevTools).
- [ ] **Memory**: Heap snapshot does not climb continuously over 60 seconds (zero GC saw-tooth).
- [ ] **Background Tab**: CPU utilization drops to 0% when switching tabs.
- [ ] **Prefers-Reduced-Motion**: Renders a single resting frame with 0 RAF triggers when reduced motion is enabled.
