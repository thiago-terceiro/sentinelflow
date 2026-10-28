---
name: sentinelflow-performance-tuning
description: >-
  Profiles and optimizes SentinelFlow and SentinelPulse for sub-15ms latency and high throughput. Use when tuning ONNX Runtime CPU inference, optimizing Redis sliding-window velocity pipelines, benchmarking LangGraph async concurrency, tuning SSE broadcaster backpressure, or profiling frontend time-travel state derivation.
---

# SentinelFlow Performance Tuning Skill

This skill provides step-by-step procedures for measuring, profiling, and optimizing high-throughput and low-latency systems in SentinelFlow and SentinelPulse.

## Latency Budgets & Target SLAs

The synchronous SentinelPulse telecom gateway operates under a strict $< 15\text{ ms}$ end-to-end latency budget:

```
Total Ingress SLA: < 15.0 ms
├── Nginx Proxy Handshake:        < 0.5 ms
├── Pre-filter Regex Rules:       < 0.05 ms
├── Redis Sliding-Window (ZSETs): < 2.0 ms
├── ONNX CPU Model Inference:     < 0.1 ms
├── Verdict & Drift Update:       < 0.2 ms
└── Network Buffer / Response:    < 1.0 ms
Total Core Processing Time:       < 3.85 ms (Headroom > 11 ms)
```

---

## Step-by-Step Performance Tuning Procedures

### Step 1: Benchmark ONNX Runtime CPU Execution
The model inference runs on CPU using ONNX Runtime with AVX-512 vectorization:
1. File: `sentinelflow/backend/app/telecom/onnx_engine.py`.
2. Inspect session options:
   ```python
   session_options = ort.SessionOptions()
   session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
   session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
   session_options.intra_op_num_threads = 4
   ```
3. Run a micro-benchmark directly:
   ```bash
   cd sentinelflow/backend
   uv run python -c "
   import time
   from app.telecom.onnx_engine import get_inference_engine
   engine = get_inference_engine()
   text = 'URGENT: Your bank account is suspended. Verify immediately at https://bit.ly/fake'
   # Warmup
   for _ in range(50): engine.classify(text)
   start = time.perf_counter()
   iterations = 1000
   for _ in range(iterations): engine.classify(text)
   elapsed = (time.perf_counter() - start) * 1000 / iterations
   print(f'Average ONNX inference latency: {elapsed:.4f} ms')
   assert elapsed < 0.2, 'Inference exceeds latency SLA!'
   "
   ```
**Verification Checkpoint**: Average latency must be $< 0.15\text{ ms}$.

### Step 2: Optimize Redis Sliding-Window Velocity Pipeline
The velocity store tracks message frequency across 10s, 60s, and 1h sliding windows:
1. File: `sentinelflow/backend/app/telecom/velocity_store.py`.
2. Ensure queries use a single pipelined block (`pipe = redis.pipeline()`):
   ```python
   # Atomic pipelining avoids 3 distinct network round trips
   async with self._client.pipeline(transaction=True) as pipe:
       for key, cutoff in [(key_10s, now - 10), (key_60s, now - 60), (key_1h, now - 3600)]:
           pipe.zremrangebyscore(key, "-inf", cutoff)
           pipe.zadd(key, {event_id: now})
           pipe.zcard(key)
           pipe.expire(key, 3600)
       results = await pipe.execute()
   ```
3. Verify that keys expire automatically to eliminate memory leaks on Redis servers under millions of unique senders.

### Step 3: Profile LangGraph Concurrency & Session Locks
During dispute investigations (`sentinelflow/backend/app/graph/nodes.py`):
1. Tools (`transactions`, `customer`, `device`, `merchant`) and analyzers must execute concurrently:
   ```python
   evidence_results = await asyncio.gather(*tool_coros, return_exceptions=True)
   ```
2. Database and ledger writes must acquire the per-investigation session lock (`session_lock`):
   ```python
   async with get_session_lock(investigation_id):
       await record_audit_event(db, ...)
   ```
3. Never use a global lock across all investigations; each investigation must have its own isolated `asyncio.Lock` to allow horizontal concurrency across distinct disputes.

### Step 4: Verify SSE Broadcaster Backpressure Safety
1. Inspect `InvestigationBroadcaster` in `sentinelflow/backend/app/services/broadcaster.py`:
   - Subscriber queues must be bounded: `asyncio.Queue(maxsize=100)`.
   - When a queue is full (slow consumer), drop old transient frames or disconnect gracefully using `try / except asyncio.QueueFull`.
   - Never allow unbounded memory growth from stalled browser clients.
2. Ensure anti-buffering HTTP headers are present on all SSE endpoints (`sentinelflow/backend/app/api/disputes.py` and `sentinelflow/ops/nginx/default.conf`):
   - `X-Accel-Buffering: no`
   - `Cache-Control: no-cache, no-transform`
   - `Connection: keep-alive`

### Step 5: Benchmark Frontend Time-Travel State Derivation
The frontend state scrubber reconstructs arbitrary historical states in-memory:
1. File: `sentinelflow/frontend/lib/deriveConsoleStateAtStep.ts`.
2. Run the native unit test suite:
   ```bash
   cd sentinelflow/frontend
   node --experimental-strip-types --test
   ```
3. Verify the state derivation benchmark:
   - Must complete 100 state derivations in $< 2.8\text{ ms}$ (average $< 0.03\text{ ms}$ per step).
   - Guarantees zero lag or frame drops while the user scrubs the timeline slider.
