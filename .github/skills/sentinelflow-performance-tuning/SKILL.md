---
name: sentinelflow-performance-tuning
description: "Profiles and optimizes SentinelFlow and SentinelPulse for sub-15ms latency and high throughput. Use when tuning ONNX Runtime CPU inference, optimizing Redis sliding-window velocity pipelines, benchmarking LangGraph async concurrency, tuning SSE broadcaster backpressure, or profiling frontend time-travel state derivation."
argument-hint: "gateway, onnx, redis, concurrency, or scrubber"
---

# SentinelFlow Performance Tuning Skill

## When To Use
- Ensuring SentinelPulse synchronous gateway satisfies its $< 15\text{ ms}$ SLA
- Profiling ONNX CPU AVX-512 inference latency ($< 0.1\text{ ms}$)
- Verifying Redis sliding-window velocity aggregation in a single pipeline ($< 2.0\text{ ms}$)
- Benchmarking frontend state scrubber time-travel derivation ($< 0.03\text{ ms}$ per step)

## Procedure

### Step 1: ONNX CPU Micro-Benchmark
```bash
cd sentinelflow/backend
uv run python -c "
import time
from app.telecom.onnx_engine import get_inference_engine
engine = get_inference_engine()
text = 'Urgent: account locked. verify at https://bit.ly/test'
start = time.perf_counter()
for _ in range(500): engine.classify(text)
avg_ms = (time.perf_counter() - start) * 1000 / 500
print(f'ONNX Latency: {avg_ms:.4f} ms')
assert avg_ms < 0.2
"
```

### Step 2: Redis Pipelined Sliding Window Check
Verify that `velocity_store.py` aggregates 10s, 60s, and 1h ZSET windows in a single `pipeline.execute()` roundtrip.

### Step 3: Frontend Time-Travel Scrubber Benchmark
```bash
cd sentinelflow/frontend
node --experimental-strip-types --test
```
Confirm `deriveConsoleStateAtStep` runs 100 derivations in $< 2.8\text{ ms}$.
