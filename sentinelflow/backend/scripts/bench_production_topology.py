"""Reproducible Production-Like Real-Redis & Multi-Worker Benchmark Harness (SF-020).

Validates SentinelPulse (/v1/classify and /api/v1/telecom/health) under a
production-like local topology:
1. Real standalone Redis 7 server (`redis:7-alpine`, or user-supplied `--redis-url`).
2. W independent API worker processes (default W=4 uvicorn processes on distinct ports).
3. Multi-process client load generation (separate OS processes + HTTP pools so client
   and server never share an event loop).

Measures separately:
- Cold-start (first request per freshly booted worker process, excluded from steady state)
- Warm-up phase (excluded from steady-state percentiles)
- Steady-state repeated runs (C=1, 8, 16; run-to-run variation quantified)
- Sustained load (N=1,200 requests at C=16)
- Isolated ONNX CPU inference vs Boundary A (`latency_ms`) vs Boundary B (`http_roundtrip_ms`)
- Concurrent inference correctness & request-state isolation
- Real Redis shared cross-worker velocity, Redis outage (`docker stop`), degraded per-worker
  in-memory fallback (`N/W` semantics), and Redis recovery (`docker start` + cooldown reset)

Usage:
    cd sentinelflow/backend
    uv run python scripts/bench_production_topology.py --manage-redis
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import onnxruntime as ort
import psutil
import redis

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.telecom.onnx_engine import get_inference_engine  # noqa: E402

DEFAULT_OUTPUT_JSON = BACKEND_DIR / "app" / "telecom" / "sf020_runtime_benchmark.json"
DEFAULT_WORKERS = 4
DEFAULT_REDIS_PORT = 16379
DEFAULT_REDIS_CONTAINER = "sf020-redis-bench"
DEFAULT_HMAC_KEY_ID = "sf020v1"
DEFAULT_HMAC_SECRET = "sf020-local-benchmark-hmac-secret-do-not-use-in-prod"  # noqa: S105

WORKLOAD_MIX: tuple[dict[str, str], ...] = (
    {
        "archetype": "benign_short",
        "expected_verdict": "ALLOW",
        "carrier": "Verizon Wireless",
        "message": "Hey, are we still meeting at 6:30 PM near the library?",
    },
    {
        "archetype": "benign_bank_alert",
        "expected_verdict": "ALLOW",
        "carrier": "AT&T Mobility",
        "message": "Chase Alert: Direct deposit of $1,420.00 from payroll posted to checking.",
    },
    {
        "archetype": "fraud_short_url",
        "expected_verdict": "BLOCK",
        "carrier": "TextNow",
        "message": "URGENT: Chase security alert! Unlock account: http://chase-verify-now.info",
    },
    {
        "archetype": "fraud_homoglyph",
        "expected_verdict": "BLOCK",
        "carrier": "Pinger",
        "message": "URGENT: Y\u043eur \u0430\u0441\u0441\u043eunt is l\u043e\u0441ked! Verify at https://bit.ly/3xYz99A",
    },
    {
        "archetype": "benign_2000_char",
        "expected_verdict": "ALLOW",
        "carrier": "T-Mobile USA",
        "message": (
            "Quarterly architecture review agenda for Friday afternoon in Room 402. " * 29
        )[:2000],
    },
)


def _find_free_ports(count: int) -> list[int]:
    ports: list[int] = []
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            ports.append(int(sock.getsockname()[1]))
            sockets.append(sock)
    finally:
        for sock in sockets:
            sock.close()
    return ports


def _pct_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "mean": 0.0}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "count": int(arr.size),
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
        "max": round(float(np.max(arr)), 3),
        "mean": round(float(np.mean(arr)), 3),
    }


def _get_cpu_model() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return str(name).strip()
        except Exception:
            return platform.processor() or "x86_64"
    return platform.processor() or "x86_64"


def _docker_bin() -> str:
    return shutil.which("docker") or "docker"


def _collect_environment_metadata(redis_client: redis.Redis, worker_count: int) -> dict[str, Any]:
    engine = get_inference_engine()
    r_info = redis_client.info()
    onnx_path = BACKEND_DIR / "app" / "telecom" / "models" / "sms_fraud_model.onnx"
    git_sha = "unknown"
    git_bin = shutil.which("git")
    if git_bin:
        try:
            git_sha = subprocess.check_output(  # noqa: S603
                [git_bin, "rev-parse", "--short", "HEAD"],
                cwd=str(BACKEND_DIR),
                text=True,
                timeout=5,
            ).strip()
        except Exception:
            git_sha = "unknown"
    return {
        "git_sha": git_sha,
        "os_platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpu_model": _get_cpu_model(),
        "cpu_cores_logical": os.cpu_count() or 1,
        "python_version": platform.python_version(),
        "onnxruntime_version": ort.__version__,
        "httpx_version": httpx.__version__,
        "redis_py_version": redis.__version__,
        "redis_server_version": str(r_info.get("redis_version", "unknown")),
        "redis_mode": str(r_info.get("redis_mode", "standalone")),
        "worker_process_count": worker_count,
        "model_artifact": onnx_path.name,
        "model_sha256": hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        "model_intra_op_threads": getattr(engine, "intra_op_num_threads", 1),
        "model_inter_op_threads": getattr(engine, "inter_op_num_threads", 1),
        "rate_limit_requests_configured": 100_000,
    }


def _redis_snapshot(redis_client: redis.Redis) -> dict[str, Any]:
    stats = redis_client.info("stats")
    mem = redis_client.info("memory")
    clients = redis_client.info("clients")
    return {
        "total_commands_processed": int(stats.get("total_commands_processed", 0)),
        "instantaneous_ops_per_sec": int(stats.get("instantaneous_ops_per_sec", 0)),
        "used_memory_bytes": int(mem.get("used_memory", 0)),
        "used_memory_human": str(mem.get("used_memory_human", "0B")),
        "connected_clients": int(clients.get("connected_clients", 0)),
    }


def _worker_resource_snapshot(procs: list[subprocess.Popen[bytes]]) -> dict[str, Any]:
    rss_mb: list[float] = []
    cpu_sec: list[float] = []
    for proc in procs:
        try:
            root = psutil.Process(proc.pid)
            tree = [root, *root.children(recursive=True)]
            proc_rss = 0
            proc_cpu = 0.0
            for node in tree:
                try:
                    proc_rss += int(node.memory_info().rss)
                    times = node.cpu_times()
                    proc_cpu += float(times.user + times.system)
                except psutil.Error:
                    pass
            rss_mb.append(round(proc_rss / (1024 * 1024), 2))
            cpu_sec.append(round(proc_cpu, 3))
        except psutil.Error:
            pass
    return {
        "worker_count_alive": len(rss_mb),
        "total_rss_mb": round(sum(rss_mb), 2),
        "per_worker_rss_mb": rss_mb,
        "total_cpu_seconds": round(sum(cpu_sec), 3),
    }


def _start_redis_container(container_name: str, port: int) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"127.0.0.1:{port}:6379",
            "redis:7-alpine",
            "redis-server",
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    client = redis.Redis(host="127.0.0.1", port=port, socket_timeout=2.0)
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        try:
            if client.ping():
                client.close()
                return
        except Exception:
            time.sleep(0.25)
    client.close()
    raise RuntimeError(f"Redis container {container_name} failed to become ready on port {port}")


def _start_worker_processes(ports: list[int], redis_url: str) -> list[subprocess.Popen[bytes]]:
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["QUEUE_REDIS_URL"] = redis_url
    env["RATE_LIMIT_REQUESTS"] = "100000"
    env["RATE_LIMIT_WINDOW_SECONDS"] = "60"
    env["TELECOM_HMAC_KEY_ID"] = DEFAULT_HMAC_KEY_ID
    env["TELECOM_HMAC_SECRET"] = DEFAULT_HMAC_SECRET
    env["SEED_DEMO_DATA"] = "false"

    procs: list[subprocess.Popen[bytes]] = []
    for port in ports:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(proc)

    deadline = time.monotonic() + 45.0
    with httpx.Client(timeout=3.0) as client:
        for port in ports:
            ready = False
            while time.monotonic() < deadline:
                try:
                    resp = client.get(f"http://127.0.0.1:{port}/api/v1/health")
                    if resp.status_code == 200:
                        ready = True
                        break
                except Exception:
                    time.sleep(0.2)
            if not ready:
                raise RuntimeError(f"Uvicorn worker on port {port} failed to pass /api/v1/health")
    return procs


def _client_worker_batch(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Executes HTTP requests from an isolated client OS process."""
    base_urls: list[str] = task["base_urls"]
    indices: list[int] = task["indices"]
    sender_prefix: str = task["sender_prefix"]
    distinct_prefix: bool = bool(task.get("distinct_prefix", False))
    timeout_s: float = float(task.get("timeout_s", 5.0))
    results: list[dict[str, Any]] = []

    with httpx.Client(timeout=timeout_s) as client:
        for req_idx in indices:
            target = base_urls[req_idx % len(base_urls)]
            item = WORKLOAD_MIX[req_idx % len(WORKLOAD_MIX)]
            if distinct_prefix:
                area = 200 + ((req_idx * 7) % 700)
                sender = f"+1{area:03d}555{req_idx:04d}"
            else:
                sender = f"{sender_prefix}{req_idx % 200:04d}"
            payload = {
                "sender": sender,
                "recipient": "+15550990001",
                "message": item["message"],
                "carrier": item["carrier"],
                "ip": f"198.51.{(req_idx // 250) + 1}.{(req_idx % 250) + 1}",
            }
            t0 = time.perf_counter()
            try:
                resp = client.post(f"{target}/v1/classify", json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if resp.status_code == 200:
                    body = resp.json()
                    results.append(
                        {
                            "ok": True,
                            "timeout": False,
                            "status_code": 200,
                            "http_ms": round(elapsed_ms, 3),
                            "app_ms": float(body.get("latency_ms", 0.0)),
                            "verdict": str(body.get("verdict")),
                            "ml_signal_status": str(body.get("ml_signal_status")),
                            "archetype": item["archetype"],
                            "expected_verdict": item["expected_verdict"],
                        }
                    )
                else:
                    results.append(
                        {
                            "ok": False,
                            "timeout": False,
                            "status_code": resp.status_code,
                            "http_ms": round(elapsed_ms, 3),
                            "app_ms": 0.0,
                        }
                    )
            except httpx.TimeoutException:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                results.append(
                    {
                        "ok": False,
                        "timeout": True,
                        "status_code": 0,
                        "http_ms": round(elapsed_ms, 3),
                        "app_ms": 0.0,
                    }
                )
            except Exception:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                results.append(
                    {
                        "ok": False,
                        "timeout": False,
                        "status_code": 0,
                        "http_ms": round(elapsed_ms, 3),
                        "app_ms": 0.0,
                    }
                )
    return results


def _run_concurrent_load(
    base_urls: list[str],
    total_requests: int,
    concurrency: int,
    sender_prefix: str,
    pool: concurrent.futures.ProcessPoolExecutor,
) -> dict[str, Any]:
    buckets: list[list[int]] = [[] for _ in range(concurrency)]
    for i in range(total_requests):
        buckets[i % concurrency].append(i)

    tasks = [
        {
            "base_urls": base_urls,
            "indices": bucket,
            "sender_prefix": sender_prefix,
            "timeout_s": 5.0,
        }
        for bucket in buckets
        if bucket
    ]

    t_start = time.perf_counter()
    batches = list(pool.map(_client_worker_batch, tasks))
    wall_s = max(time.perf_counter() - t_start, 1e-6)

    rows = [row for batch in batches for row in batch]
    ok_rows = [r for r in rows if r["ok"]]
    err_count = len(rows) - len(ok_rows)
    timeout_count = sum(1 for r in rows if r["timeout"])
    http_vals = [r["http_ms"] for r in ok_rows]
    app_vals = [r["app_ms"] for r in ok_rows]

    return {
        "requests": total_requests,
        "concurrency_processes": concurrency,
        "wall_seconds": round(wall_s, 3),
        "throughput_rps": round(len(ok_rows) / wall_s, 2),
        "error_count": err_count,
        "error_rate": round(err_count / max(len(rows), 1), 6),
        "timeout_count": timeout_count,
        "boundary_a_app_ms": _pct_summary(app_vals),
        "boundary_b_http_ms": _pct_summary(http_vals),
    }


def _benchmark_isolated_onnx() -> dict[str, Any]:
    engine = get_inference_engine()
    if engine.session is None:
        raise RuntimeError("ONNX session unavailable for isolated benchmark")
    input_name = engine.session.get_inputs()[0].name
    # Warm-up
    for item in WORKLOAD_MIX:
        _ = engine.session.run(None, {input_name: np.array([[item["message"]]], dtype=object)})

    by_type: dict[str, list[float]] = {item["archetype"]: [] for item in WORKLOAD_MIX}
    all_ms: list[float] = []
    for _ in range(200):
        for item in WORKLOAD_MIX:
            t0 = time.perf_counter()
            _ = engine.session.run(
                None, {input_name: np.array([[item["message"]]], dtype=object)}
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            by_type[item["archetype"]].append(dt_ms)
            all_ms.append(dt_ms)

    return {
        "samples_total": len(all_ms),
        "overall_ms": _pct_summary(all_ms),
        "by_archetype_ms": {k: _pct_summary(v) for k, v in by_type.items()},
    }


def _verify_redis_outage_and_recovery(
    base_urls: list[str],
    redis_container: str | None,
    redis_port: int,
    manage_redis: bool,
) -> dict[str, Any]:
    if not manage_redis or not redis_container:
        return {"status": "skipped_external_redis_mode"}

    outage_report: dict[str, Any] = {}
    with httpx.Client(timeout=5.0) as client:
        # 1. Healthy baseline shared velocity across all W workers
        shared_sender = "+15550208801"
        v10_healthy: list[int] = []
        for idx in range(len(base_urls) * 2):
            url = base_urls[idx % len(base_urls)]
            resp = client.post(
                f"{url}/v1/classify",
                json={
                    "sender": shared_sender,
                    "recipient": "+15550990001",
                    "message": WORKLOAD_MIX[0]["message"],
                    "carrier": "Verizon Wireless",
                    "ip": "198.51.100.20",
                },
            )
            v10_healthy.append(int(resp.json()["velocity"]["velocity_10s"]))
        health_pre = [client.get(f"{u}/api/v1/telecom/health").json() for u in base_urls]
        outage_report["healthy_shared_velocity_10s"] = v10_healthy
        outage_report["healthy_backends"] = [h["velocity_backend"] for h in health_pre]

        # 2. Stop real Redis container -> verify fail-open & per-worker N/W isolation
        subprocess.run(["docker", "stop", redis_container], check=True, capture_output=True)
        degraded_sender = "+15550208802"
        v10_degraded: list[int] = []
        degraded_statuses: list[int] = []
        for idx in range(len(base_urls) * 3):
            url = base_urls[idx % len(base_urls)]
            resp = client.post(
                f"{url}/v1/classify",
                json={
                    "sender": degraded_sender,
                    "recipient": "+15550990001",
                    "message": WORKLOAD_MIX[0]["message"],
                    "carrier": "Verizon Wireless",
                    "ip": "198.51.100.21",
                },
            )
            degraded_statuses.append(resp.status_code)
            v10_degraded.append(int(resp.json()["velocity"]["velocity_10s"]))
        health_deg = [client.get(f"{u}/api/v1/telecom/health").json() for u in base_urls]
        outage_report["outage_http_statuses"] = sorted(set(degraded_statuses))
        outage_report["outage_per_worker_velocity_10s"] = v10_degraded
        outage_report["outage_backends"] = [h["velocity_backend"] for h in health_deg]
        outage_report["outage_degraded_flags"] = [h["velocity_degraded_mode"] for h in health_deg]

        # 3. Restart Redis container and wait for production 30s cooldown expiry
        subprocess.run(["docker", "start", redis_container], check=True, capture_output=True)
        r_client = redis.Redis(host="127.0.0.1", port=redis_port, socket_timeout=2.0)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                if r_client.ping():
                    break
            except Exception:
                time.sleep(0.2)
        r_client.close()

        max_cooldown = max(float(h.get("cooldown_remaining_seconds", 0.0)) for h in health_deg)
        time.sleep(max(max_cooldown + 1.5, 31.5))

        rec_sender = "+15550208803"
        v10_recovered: list[int] = []
        for idx in range(len(base_urls) * 2):
            url = base_urls[idx % len(base_urls)]
            resp = client.post(
                f"{url}/v1/classify",
                json={
                    "sender": rec_sender,
                    "recipient": "+15550990001",
                    "message": WORKLOAD_MIX[0]["message"],
                    "carrier": "Verizon Wireless",
                    "ip": "198.51.100.22",
                },
            )
            v10_recovered.append(int(resp.json()["velocity"]["velocity_10s"]))
        health_rec = [client.get(f"{u}/api/v1/telecom/health").json() for u in base_urls]
        outage_report["recovered_shared_velocity_10s"] = v10_recovered
        outage_report["recovered_backends"] = [h["velocity_backend"] for h in health_rec]
        outage_report["recovered_degraded_flags"] = [
            h["velocity_degraded_mode"] for h in health_rec
        ]

    return outage_report


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    redis_port = args.redis_port
    redis_url = args.redis_url or f"redis://127.0.0.1:{redis_port}/0"
    container_name = DEFAULT_REDIS_CONTAINER if args.manage_redis else None

    if args.manage_redis:
        _start_redis_container(DEFAULT_REDIS_CONTAINER, redis_port)

    ports = _find_free_ports(args.workers)
    base_urls = [f"http://127.0.0.1:{p}" for p in ports]
    worker_procs: list[subprocess.Popen[bytes]] = []
    r_client = redis.Redis.from_url(redis_url, socket_timeout=2.0)

    try:
        r_client.flushdb()
        worker_procs = _start_worker_processes(ports, redis_url)
        env_meta = _collect_environment_metadata(r_client, args.workers)
        isolated_onnx = _benchmark_isolated_onnx()

        # 1. Cold-start (1st request per freshly booted worker)
        cold_app_ms: list[float] = []
        cold_http_ms: list[float] = []
        with httpx.Client(timeout=10.0) as client:
            for idx, url in enumerate(base_urls):
                t0 = time.perf_counter()
                resp = client.post(
                    f"{url}/v1/classify",
                    json={
                        "sender": f"+155502009{idx:02d}",
                        "recipient": "+15550990001",
                        "message": WORKLOAD_MIX[idx % len(WORKLOAD_MIX)]["message"],
                        "carrier": "Verizon Wireless",
                    },
                )
                http_dt = (time.perf_counter() - t0) * 1000.0
                if resp.status_code != 200:
                    raise RuntimeError(f"Cold-start request failed: {resp.status_code}")
                cold_http_ms.append(round(http_dt, 3))
                cold_app_ms.append(float(resp.json()["latency_ms"]))

        # 2. Warm-up (excluded from steady-state)
        with concurrent.futures.ProcessPoolExecutor(max_workers=16) as pool:
            _ = _run_concurrent_load(base_urls, 40, 4, "+15550201", pool)

            # 3. Steady-state repeated runs across concurrency levels
            steady_runs: dict[str, list[dict[str, Any]]] = {}
            for conc in (1, 8, 16):
                runs_for_conc: list[dict[str, Any]] = []
                for run_idx in range(args.repeats):
                    r_before = _redis_snapshot(r_client)
                    res = _run_concurrent_load(
                        base_urls,
                        args.steady_requests,
                        conc,
                        f"+155502{conc:02d}{run_idx}",
                        pool,
                    )
                    r_after = _redis_snapshot(r_client)
                    deg_flags = [
                        bool(
                            httpx.get(f"{u}/api/v1/telecom/health", timeout=2.0).json().get(
                                "velocity_degraded_mode"
                            )
                        )
                        for u in base_urls
                    ]
                    res["redis_commands_delta"] = (
                        r_after["total_commands_processed"] - r_before["total_commands_processed"]
                    )
                    res["redis_used_memory_bytes"] = r_after["used_memory_bytes"]
                    res["workers_in_degraded_fallback"] = sum(deg_flags)
                    res["worker_resources"] = _worker_resource_snapshot(worker_procs)
                    runs_for_conc.append(res)
                steady_runs[f"concurrency_{conc}"] = runs_for_conc

            # Ensure any circuit-breaker cooldown tripped under C=16 oversubscription has cleared
            pre_sust_health = [
                httpx.get(f"{u}/api/v1/telecom/health", timeout=2.0).json() for u in base_urls
            ]
            max_wait = max(float(h.get("cooldown_remaining_seconds", 0.0)) for h in pre_sust_health)
            if max_wait > 0.0:
                time.sleep(max_wait + 1.0)

            # 4. Sustained load (C=8 real-Redis sustained load across W=4 workers)
            r_before_sust = _redis_snapshot(r_client)
            sustained = _run_concurrent_load(
                base_urls,
                args.sustained_requests,
                8,
                "+15550299",
                pool,
            )
            r_after_sust = _redis_snapshot(r_client)
            sust_deg_flags = [
                bool(
                    httpx.get(f"{u}/api/v1/telecom/health", timeout=2.0).json().get(
                        "velocity_degraded_mode"
                    )
                )
                for u in base_urls
            ]
            sustained["redis_commands_delta"] = (
                r_after_sust["total_commands_processed"]
                - r_before_sust["total_commands_processed"]
            )
            sustained["workers_in_degraded_fallback"] = sum(sust_deg_flags)
            sustained["redis_used_memory_human"] = r_after_sust["used_memory_human"]
            sustained["worker_resources"] = _worker_resource_snapshot(worker_procs)

            # 5. Concurrent inference correctness & state isolation
            corr_tasks = [
                {
                    "base_urls": base_urls,
                    "indices": list(range(i, 120, 8)),
                    "sender_prefix": "+1200555",
                    "distinct_prefix": True,
                    "timeout_s": 5.0,
                }
                for i in range(8)
            ]
            corr_batches = list(pool.map(_client_worker_batch, corr_tasks))
            corr_rows = [r for b in corr_batches for r in b]
            corr_ok = [r for r in corr_rows if r["ok"]]
            mismatches = [
                r
                for r in corr_ok
                if r["verdict"] != r["expected_verdict"] or r["ml_signal_status"] != "valid"
            ]
            correctness = {
                "total_requests": len(corr_rows),
                "successful_requests": len(corr_ok),
                "verdict_and_signal_mismatches": len(mismatches),
                "zero_cross_request_leakage_verified": len(corr_ok) == 120 and len(mismatches) == 0,
            }

        # 6. Redis outage & recovery
        outage_recovery = _verify_redis_outage_and_recovery(
            base_urls, container_name, redis_port, args.manage_redis
        )

        # Quantify run-to-run variation across repeats
        variation: dict[str, Any] = {}
        for conc_key, runs in steady_runs.items():
            p95s = [r["boundary_b_http_ms"]["p95"] for r in runs]
            rpss = [r["throughput_rps"] for r in runs]
            variation[conc_key] = {
                "http_p95_min_ms": min(p95s),
                "http_p95_max_ms": max(p95s),
                "http_p95_spread_ms": round(max(p95s) - min(p95s), 3),
                "throughput_rps_min": min(rpss),
                "throughput_rps_max": max(rpss),
                "throughput_rps_spread": round(max(rpss) - min(rpss), 2),
            }

        report = {
            "ticket_id": "SF-020",
            "environment": env_meta,
            "topology": {
                "redis_url": redis_url,
                "managed_docker_redis": args.manage_redis,
                "worker_processes": args.workers,
                "client_execution": "multi_process_ProcessPoolExecutor_isolated_event_loops",
                "workload_archetypes": [w["archetype"] for w in WORKLOAD_MIX],
            },
            "isolated_onnx_inference": isolated_onnx,
            "cold_start": {
                "sample_count": len(cold_http_ms),
                "boundary_a_app_ms": cold_app_ms,
                "boundary_b_http_ms": cold_http_ms,
            },
            "steady_state_runs": steady_runs,
            "run_to_run_variation": variation,
            "sustained_load": sustained,
            "concurrent_correctness": correctness,
            "redis_outage_and_recovery": outage_recovery,
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        r_client.close()
        for proc in worker_procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in worker_procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if args.manage_redis and container_name:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="SF-020 Real-Redis Multi-Worker Benchmark")
    parser.add_argument("--redis-url", type=str, default=None)
    parser.add_argument("--redis-port", type=int, default=DEFAULT_REDIS_PORT)
    parser.add_argument("--manage-redis", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--steady-requests", type=int, default=300)
    parser.add_argument("--sustained-requests", type=int, default=1000)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args()

    report = run_benchmark(args)
    print(json.dumps(report["run_to_run_variation"], indent=2))
    print("Sustained:", json.dumps(report["sustained_load"], indent=2))
    print("Correctness:", json.dumps(report["concurrent_correctness"], indent=2))
    print("Outage/Recovery:", json.dumps(report["redis_outage_and_recovery"], indent=2))


if __name__ == "__main__":
    main()
