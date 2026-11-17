# SF-020 — Production-Like Runtime & Concurrency Validation Report

**Linear Ticket:** `AI-33` (`SF-020`)  
**Status:** Complete (With Reproducible Topology Harness & Justified Timeout Fix)  
**Machine-Readable Evidence:** `sentinelflow/backend/app/telecom/sf020_runtime_benchmark.json`  
**Harness Command:** `cd sentinelflow/backend && uv run python scripts/bench_production_topology.py --manage-redis`

---

## 1. Test Topology & Environment Provenance

* **Host Hardware & OS:** Windows 11 (`AMD64`), `12th Gen Intel(R) Core(TM) i5-12450H` (`12` logical CPUs), commit `edacd8f`.
* **Runtime Versions:** Python `3.12.7`, `onnxruntime 1.31.0` (`intra_op=1, inter_op=1`), `httpx 0.28.1`, `redis-py 5.3.1`.
* **Redis Server:** Real standalone Docker `redis:7-alpine` (**Redis `7.4.11`**) on `127.0.0.1:16379`.
* **Application Tier:** **`W=4` independent `uvicorn` OS worker processes** on distinct loopback ports (`APP_ENV=development`, `QUEUE_REDIS_URL=redis://127.0.0.1:16379/0`, `RATE_LIMIT_REQUESTS=100000` to isolate gateway classification from the in-memory API rate limiter).
* **Load Generation:** Independent client OS processes via `concurrent.futures.ProcessPoolExecutor` using blocking `httpx.Client` pools so client threads/loops never share an event loop with the API servers.
* **Model Artifact:** `sms_fraud_model.onnx` (SHA-256 `824c6c2c254791205184efadd8f0b2dc43f22e7222b411e75c2b99c340a9604b`, frozen `SF-018` retained under `SF-019` no-change decision).
* **Workload Mix:** Balanced 5-archetype mix (`benign_short`, `benign_bank_alert`, `fraud_short_url`, `fraud_homoglyph`, `benign_2000_char` up to `2,000` chars).

---

## 2. Production Bug Found & Fixed During Validation

When first executing the real-Redis multi-worker harness, **all 4 workers immediately failed over to `local_memory_fallback`** on the first request (`redis_commands_delta = 3` across sustained load), and isolated connection testing measured `10/10` failures in `~1ms` with `TimeoutError('Timeout connecting to server')`.

* **Root Cause:** `RedisVelocityStore._get_client()` previously pinned `socket_timeout=0.015` and `socket_connect_timeout=0.015`. On Windows (`15.625 ms` default OS timer resolution), sub-20ms asyncio timeouts alias to immediate expirations during TCP/Docker NAT connection setup, permanently tripping the 30-second in-memory circuit breaker even against a healthy Redis instance.
* **Justified Fix (`sentinelflow/backend/app/telecom/velocity_store.py`):** Raised `socket_timeout` to `0.050` (50 ms I/O budget) and `socket_connect_timeout` to `0.100` (100 ms connect handshake budget), covered by unit regression test `test_sf020_redis_velocity_store_timeouts_avoid_sub_tick_truncation`. After the fix, healthy `redis:7-alpine` pipelines succeeded with `0` degraded workers across `C=1`, `C=8`, and `1,000`-request sustained load (`21,619` Redis commands).

---

## 3. Separated Latency, Throughput & Resource Measurements

### 3.1 Isolated ONNX CPU Inference vs. Cold-Start vs. Steady-State vs. Sustained

| Phase | Conditions & Redis State | Boundary A (`app latency_ms`) | Boundary B (`http_roundtrip_ms`) | Throughput & Spread |
|---|---|---|---|---|
| **Isolated ONNX `session.run()`** (`N=1,000`) | Pure C++/AVX-512 in-process (after warm-up) | `p50=0.067`, `p95=0.176`, `p99=0.278` ms (`2000-char p95=0.251 ms`) | N/A | In-process ML kernel only (NOT HTTP SLA) |
| **Worker Cold-Start** (`N=4`) | First HTTP request per newly booted worker; excludes steady-state | `3.921 – 4.659 ms` | **`25.284 – 50.184 ms`** | Excluded from steady-state |
| **Steady-State `C=1`** (`N=300 × 2`) | `0/4` degraded workers (`6,483` Redis cmds/run) | `p50=1.615–1.677`, `p95=2.085–2.373` ms | `p50=4.060–4.213`, **`p95=4.962–5.569`**, `p99=6.433–7.995` ms | `198.68–205.85 RPS` (`p95 spread 0.607 ms`) |
| **Steady-State `C=8`** (`N=300 × 2`) | `0/4` degraded workers (`6,483` Redis cmds/run) | `p50=2.454–2.652`, `p95=3.347–3.557` ms | `p50=6.003–6.644`, **`p95=7.613–8.022`**, `p99=8.386–9.077` ms | `220.24–237.30 RPS` (`p95 spread 0.409 ms`) |
| **Oversubscribed Stress `C=16` (Run 1)** | `16` client procs + `4` workers on `12` logical CPUs; tripped 50ms Redis circuit breaker (`4/4` degraded, `3,483` Redis cmds) | `p50=3.649`, `p95=27.723`, `p99=45.115` ms | `p50=8.224`, **`p95=34.265`**, `p99=54.576` ms | `88.26 RPS`, `0` HTTP errors/timeouts |
| **Oversubscribed Stress `C=16` (Run 2)** | Inside 30s cooldown from Run 1 (`4/4` in-memory fallback, `3` Redis cmds) | `p50=0.941`, `p95=2.171` ms | `p50=6.941`, `p95=11.627`, `p99=21.737` ms | `82.18 RPS` (`C=16 p95 spread 22.638 ms`) |
| **Sustained Real-Redis Load (`N=1,000, C=8`)** | Post-cooldown recovery; **`0/4` degraded workers**, `21,619` Redis cmds | `p50=2.354`, `p95=4.271`, `p99=6.689` ms (`max=10.189 ms`) | `p50=7.147`, **`p95=11.235`**, `p99=15.983` ms (`max=24.266 ms`) | **`666.01 RPS`** (`1.501 s`), `0` errors |

### 3.2 Resource Utilization
* **Uvicorn Workers (`W=4`):** Total process-tree RSS **`965.79 – 970.22 MB`** (`~241–243 MB` per worker), `4/4` alive across all runs, `total_cpu_seconds = 82.844 s` cumulative across the full benchmark suite.
* **Redis `7.4.11`:** `2.64M` (`2,216,712+` peak bytes reported during `C=16` / sustained window) used memory across sustained + steady sliding windows (`21,619` commands during the 1,000-request sustained burst).

---

## 4. Concurrent Correctness & Real-Redis Outage / Recovery

* **Concurrent Request Isolation (`N=120`, `8` client processes, distinct carrier NPA prefixes):** `120 / 120` HTTP `200`, **`0` verdict or `ml_signal_status` mismatches**, **`zero_cross_request_leakage_verified = true`**.
* **Real-Redis Outage & Recovery:**
  1. **Healthy (`W=4` -> real `redis:7-alpine`):** All 4 workers reported `velocity_backend="redis"`; 8 interleaved requests to one sender produced monotonic shared velocity `[1, 2, 3, 4, 5, 6, 7, 8]`.
  2. **Outage (`docker stop sf020-redis-bench`):** All 12 requests returned **HTTP `200` fail-open** (`0` dropped messages); all 4 workers reported `velocity_backend="local_memory_fallback"`, `velocity_degraded_mode=true`, and observed per-worker `N/W` velocity `[1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]`.
  3. **Recovery (`docker start` + 31.5 s cooldown wait):** All 4 workers automatically reconnected to Redis, cleared `velocity_degraded_mode=false`, and resumed global shared counting `[1, 2, 3, 4, 5, 6, 7, 8]`.

---

## 5. Honest Performance Scope & Limitations

1. **No Universal `<15ms` HTTP Claim:** On this local Windows 11 host (`W=4` + standalone `redis:7-alpine`), end-to-end HTTP `p95` stays under 15 ms (`4.962–11.235 ms`) through `C=8` concurrent client processes (`666.01 RPS` sustained) after fixing `socket_connect_timeout`, **but exceeds 15 ms during cold starts (`25.3–50.2 ms`) and under CPU-oversubscribed `C=16` burst load (`34.265 ms p95` + circuit-breaker trip at 50 ms)**.
2. **In-Memory API Rate Limiter:** For this benchmark `RATE_LIMIT_REQUESTS` was set to `100000`. As documented in `README.md`, `InMemoryRateLimiter` remains per-worker (`4 ×` effective limit across 4 processes) unless backed by Redis in a distributed deployment.
3. **CI Independence:** Automated CI covers `test_sf020_redis_velocity_store_timeouts_avoid_sub_tick_truncation` deterministically without introducing flaky machine-timing gates; full multi-worker benchmarks run on-demand via `scripts/bench_production_topology.py --manage-redis`.
