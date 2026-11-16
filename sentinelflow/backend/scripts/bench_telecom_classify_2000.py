"""Reproducible 2,000-character latency benchmark for SentinelPulse (/v1/classify).

Measures two distinct execution harnesses at the 2,000-character application-level
contract boundary and separates internal processing (Boundary A) from caller-observed
HTTP round-trip latency (Boundary B):

1. In-process ASGI + component microbenchmark (N=100 sequential samples per payload
   across 11 benign, fraud, homoglyph, multilingual, and high-PII-density payloads;
   Note: at N=100 per payload, p99 represents the 99th/100th ordered observation).
2. Loopback TCP/HTTP Uvicorn server benchmark (N=300 samples per concurrency level
   across concurrency = 1, 4, 8 over http://127.0.0.1:<ephemeral_port>/v1/classify),
   evaluating both the in-process fake-Redis pipeline simulation path (_FakeRedisClient,
   24 ZSET ops/request, no external Redis server/network RTT) and the local in-memory
   fallback path.

Timing Boundaries & Contractual Status (2,000-Character Payloads):
- Linear AI-18 (SF-015) Step 3 ReDoS Guard: evaluate_heuristics() < 15 ms on 2,000-char
  pathological strings -> PASS.
- Boundary A (Internal server-side processing: _process_single_message() t_start..t_end,
  returned as response latency_ms / endpoint_latency_ms) -> PASS (< 15 ms across both
  cb64ff2 [in-process agg p95 6.254-7.128 ms; loopback p95 5.488-8.815 ms] and e12734d
  [in-process agg p95 1.937-2.129 ms; loopback p95 1.748-3.725 ms] local runs).
- Boundary B (Architectural end-to-end HTTP <15 ms target, measured as asgi_roundtrip_ms
  and loopback_http_ms) -> NOT ESTABLISHED: local loopback conc=1 p95 passed in the
  e12734d run (6.228-7.633 ms) but exceeded 15 ms in the cb64ff2 run (17.259-17.793 ms),
  while shared-event-loop conc=4 (25.280-26.094 ms in e12734d; 60.852-61.257 ms in
  cb64ff2) and conc=8 (54.984-63.106 ms in e12734d; 121.061-124.160 ms in cb64ff2)
  reflect HTTP/FastAPI/Pydantic/post-t_end JsonFormatter overhead plus non-representative
  same-event-loop client/server queuing.
- Unverified Scope: Live Redis server network RTT and independent-process / multi-worker
  concurrency are UNVERIFIED in this single-process, fake-Redis/in-memory harness.

Usage:
    cd sentinelflow/backend
    uv run python scripts/bench_telecom_classify_2000.py
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import socket
import sys
import time
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import uvicorn

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.telecom.onnx_engine import (  # noqa: E402
    evaluate_heuristics,
    get_inference_engine,
    redact_sms_pii,
)
from app.telecom.velocity_store import get_velocity_store  # noqa: E402


class _FakePipeline:
    async def __aenter__(self) -> _FakePipeline:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def zremrangebyscore(self, *_args: object) -> None:
        return None

    def zadd(self, *_args: object) -> None:
        return None

    def expire(self, *_args: object) -> None:
        return None

    def zcard(self, *_args: object) -> None:
        return None

    async def execute(self) -> list[int]:
        await asyncio.sleep(0)
        return [0, 1, 1, 1] * 6


class _FakeRedisClient:
    def pipeline(self, transaction: bool = False) -> _FakePipeline:
        if transaction is not False:
            raise RuntimeError("Expected transaction=False")
        return _FakePipeline()


def _pad2000(seed: str) -> str:
    repeats = (2000 // len(seed)) + 2
    out = (seed * repeats)[:2000]
    if len(out) != 2000:
        raise RuntimeError(f"Expected 2000 chars, got {len(out)}")
    return out


PAYLOADS: dict[str, str] = {
    "benign_prose": _pad2000(
        "Hello team, the quarterly architecture review is scheduled "
        "for Friday at 2:30 PM in Room 402. "
    ),
    "benign_numeric": _pad2000(
        "Order #849201 shipped in 2026 for $1,240.50 EUR 89.99 GBP 45.00 with 15 items in 3 boxes. "
    ),
    "fraud_lockout": _pad2000(
        "URGENT: Your bank account has been suspended due to unauthorized "
        "login attempts! Verify immediately at https://chase-verify-alert.xyz/login. "
    ),
    "fraud_irs_tax": _pad2000(
        "FINAL NOTICE: IRS tax warrant issued for arrest due to unpaid "
        "federal tax penalty. Pay immediately via https://irs-gov-settlement.top/pay. "
    ),
    "fraud_crypto": _pad2000(
        "Guaranteed 250% daily crypto return on USDT staking pool! "
        "Claim VIP airdrop bonus at https://t.me/crypto_whale_pump_vip. "
    ),
    "homoglyph_mixed": _pad2000(
        "URGENT: Y\u043eur \u0430\u0441\u0441\u043eunt is l\u043e\u0441ked! "
        "V\u0435rify p\u0430yment at https://bit.ly/3xYz99A immediately. "
    ),
    "multilingual_pt_es": _pad2000(
        "Ol\u00e1, sua consulta m\u00e9dica foi confirmada para amanh\u00e3 \u00e0s 14h30. "
        "Hola, tu pedido estar\u00e1 listo ma\u00f1ana por la tarde. "
    ),
    "pii_otp_dense": _pad2000(
        "Security alert: Your one-time verification code is 482910 and "
        "backup PIN: 7391 or OTP 9182-7341. Do not share this code. "
    ),
    "pii_phone_dense": _pad2000(
        "Contact support at +1-800-555-0199, (415) 555-0199, 800.555.0199, "
        "or international +44 20 7946 0958 and 4155550199. "
    ),
    "pii_card_ssn_email": _pad2000(
        "Billing ref: card 4111-1111-1111-1111, SSN 123-45-6789, "
        "tax ID 123456789, email billing.support@example.com. "
    ),
    "pii_all_combined": _pad2000(
        "URGENT: Account locked! Call +1-800-555-0199 or 4155550199 with PIN 4829, "
        "SSN 123-45-6789, card 4111 1111 1111 1111, email sec.ops@example.com "
        "at https://bit.ly/claim99. "
    ),
}


def _pct_stats(values: list[float]) -> dict[str, float]:
    arr = np.array(values, dtype=np.float64)
    return {
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
        "max": round(float(np.max(arr)), 3),
    }


async def _run_inprocess_asgi_benchmark() -> dict[str, Any]:
    engine = get_inference_engine()
    vstore = get_velocity_store()
    transport = httpx.ASGITransport(app=app)

    engine.predict(PAYLOADS["pii_all_combined"])
    redact_sms_pii(PAYLOADS["pii_all_combined"])

    results: dict[str, Any] = {}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/v1/classify",
            json={
                "sender": "+15550001111",
                "recipient": "+14155550100",
                "ip": "198.51.100.10",
                "carrier": "Verizon Wireless",
                "message": PAYLOADS["pii_all_combined"],
            },
        )

        for mode_idx, (mode, use_fallback) in enumerate(
            [("inprocess_fake_redis_pipeline", False), ("local_memory_fallback", True)]
        ):
            vstore._use_in_memory_fallback = use_fallback
            cast(Any, vstore)._get_client = lambda: _FakeRedisClient()
            mode_results: dict[str, Any] = {}
            all_ep: list[float] = []
            all_http: list[float] = []
            for p_idx, (name, msg) in enumerate(PAYLOADS.items()):
                red_t: list[float] = []
                heur_t: list[float] = []
                pred_t: list[float] = []
                ep_t: list[float] = []
                http_t: list[float] = []
                client_ip = f"198.51.{100 + mode_idx}.{10 + p_idx}"
                for _ in range(100):
                    t0 = time.perf_counter()
                    redact_sms_pii(msg)
                    red_t.append((time.perf_counter() - t0) * 1000.0)

                    t0 = time.perf_counter()
                    evaluate_heuristics(msg)
                    heur_t.append((time.perf_counter() - t0) * 1000.0)

                    t0 = time.perf_counter()
                    engine.predict(msg)
                    pred_t.append((time.perf_counter() - t0) * 1000.0)

                    t0 = time.perf_counter()
                    resp = await client.post(
                        "/v1/classify",
                        headers={"X-Real-IP": client_ip},
                        json={
                            "sender": "+15550001111",
                            "recipient": "+14155550100",
                            "ip": client_ip,
                            "carrier": "Verizon Wireless",
                            "message": msg,
                        },
                    )
                    http_t.append((time.perf_counter() - t0) * 1000.0)
                    if resp.status_code != 200:
                        raise RuntimeError(f"Status {resp.status_code}: {resp.text}")
                    ep_t.append(float(resp.json()["latency_ms"]))
                all_ep.extend(ep_t)
                all_http.extend(http_t)
                mode_results[name] = {
                    "redact_ms": _pct_stats(red_t),
                    "heuristics_ms": _pct_stats(heur_t),
                    "predict_ms": _pct_stats(pred_t),
                    "endpoint_latency_ms": _pct_stats(ep_t),
                    "asgi_roundtrip_ms": _pct_stats(http_t),
                }
            mode_results["AGGREGATE_ALL_1100"] = {
                "endpoint_latency_ms": _pct_stats(all_ep),
                "asgi_roundtrip_ms": _pct_stats(all_http),
            }
            results[mode] = mode_results
    return results


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _run_uvicorn_loopback_benchmark() -> dict[str, Any]:
    port = _get_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.02)

    vstore = get_velocity_store()
    payload_list = list(PAYLOADS.values())
    sample_count = 300
    concurrency_levels = (1, 4, 8)
    uvicorn_results: dict[str, Any] = {}

    try:
        limits = httpx.Limits(max_connections=32, max_keepalive_connections=32)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}",
            limits=limits,
            timeout=10.0,
        ) as client:
            # Warmup TCP socket pool & Uvicorn HTTP parser
            for i in range(16):
                await client.post(
                    "/v1/classify",
                    headers={"X-Real-IP": f"203.0.113.{1 + (i % 8)}"},
                    json={
                        "sender": "+15550002222",
                        "recipient": "+14155550100",
                        "ip": "203.0.113.1",
                        "carrier": "Verizon Wireless",
                        "message": PAYLOADS["pii_all_combined"],
                    },
                )

            for mode_idx, (mode, use_fallback) in enumerate(
                [("inprocess_fake_redis_pipeline", False), ("local_memory_fallback", True)]
            ):
                vstore._use_in_memory_fallback = use_fallback
                cast(Any, vstore)._get_client = lambda: _FakeRedisClient()
                mode_summary: dict[str, Any] = {}

                for conc in concurrency_levels:
                    sem = asyncio.Semaphore(conc)
                    ep_latencies: list[float] = []
                    tcp_http_latencies: list[float] = []

                    async def _one_call(
                        idx: int,
                        _sem: asyncio.Semaphore = sem,
                        _conc: int = conc,
                        _m: int = mode_idx,
                        _ep: list[float] = ep_latencies,
                        _tcp: list[float] = tcp_http_latencies,
                    ) -> None:
                        msg = payload_list[idx % len(payload_list)]
                        # Spread across synthetic IPs to avoid rate limiter throttling
                        ip_addr = f"192.0.{10 + _m * 10 + _conc}.{1 + (idx % 200)}"
                        async with _sem:
                            t0 = time.perf_counter()
                            resp = await client.post(
                                "/v1/classify",
                                headers={"X-Real-IP": ip_addr},
                                json={
                                    "sender": f"+1555010{idx % 1000:04d}",
                                    "recipient": "+14155550100",
                                    "ip": ip_addr,
                                    "carrier": "Verizon Wireless",
                                    "message": msg,
                                },
                            )
                            elapsed_ms = (time.perf_counter() - t0) * 1000.0
                            if resp.status_code != 200:
                                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
                            body = resp.json()
                            _ep.append(float(body["latency_ms"]))
                            _tcp.append(elapsed_ms)

                    t_batch_start = time.perf_counter()
                    await asyncio.gather(*[_one_call(i) for i in range(sample_count)])
                    wall_s = time.perf_counter() - t_batch_start

                    mode_summary[f"concurrency_{conc}"] = {
                        "samples": sample_count,
                        "concurrency": conc,
                        "throughput_rps": round(sample_count / max(wall_s, 1e-6), 1),
                        "endpoint_latency_ms": _pct_stats(ep_latencies),
                        "loopback_http_ms": _pct_stats(tcp_http_latencies),
                    }
                uvicorn_results[mode] = mode_summary
    finally:
        server.should_exit = True
        await server_task

    return uvicorn_results


async def main() -> None:
    import logging

    from app.logging import JsonFormatter

    class _FormattingMemoryHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.setFormatter(JsonFormatter())
            self.formatted_count = 0

        def emit(self, record: logging.LogRecord) -> None:
            _ = self.format(record)
            self.formatted_count += 1

    root_logger = logging.getLogger()
    mem_handler = _FormattingMemoryHandler()
    root_logger.handlers = [mem_handler]
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    asgi_res = await _run_inprocess_asgi_benchmark()
    uvicorn_res = await _run_uvicorn_loopback_benchmark()
    max_heur_p95 = max(
        float(payload_stats["heuristics_ms"]["p95"])
        for mode_stats in asgi_res.values()
        for key, payload_stats in mode_stats.items()
        if key != "AGGREGATE_ALL_1100"
    )
    max_boundary_a_p95 = max(
        float(conc_stats["endpoint_latency_ms"]["p95"])
        for mode_stats in uvicorn_res.values()
        for conc_stats in mode_stats.values()
    )
    max_boundary_b_conc1_p95 = max(
        float(mode_stats["concurrency_1"]["loopback_http_ms"]["p95"])
        for mode_stats in uvicorn_res.values()
    )
    max_boundary_b_all_p95 = max(
        float(conc_stats["loopback_http_ms"]["p95"])
        for mode_stats in uvicorn_res.values()
        for conc_stats in mode_stats.values()
    )
    report = {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "payload_length_chars": 2000,
            "audit_records_json_formatted": mem_handler.formatted_count,
        },
        "contract_and_evidence_classification": {
            "sf015_ai18_heuristics_redos_guard_lt_15ms": (
                "PASS" if max_heur_p95 < 15.0 else "FAIL"
            ),
            "boundary_a_internal_process_single_message_lt_15ms": (
                "PASS" if max_boundary_a_p95 < 15.0 else "FAIL"
            ),
            "boundary_b_local_loopback_conc1_p95_lt_15ms_this_run": (
                "PASS_LOCAL_ONLY" if max_boundary_b_conc1_p95 < 15.0 else "FAIL"
            ),
            "boundary_b_local_loopback_all_tested_conc_p95_lt_15ms": (
                "PASS_LOCAL_ONLY" if max_boundary_b_all_p95 < 15.0 else "FAIL"
            ),
            "boundary_b_end_to_end_http_lt_15ms_target": "NOT_ESTABLISHED",
            "live_redis_network_rtt": "UNVERIFIED",
            "independent_process_multi_worker_concurrency": "UNVERIFIED",
        },
        "inprocess_asgi_n100_per_payload": asgi_res,
        "loopback_uvicorn_tcp_n300_per_concurrency": uvicorn_res,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
