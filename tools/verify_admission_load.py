#!/usr/bin/env python3
"""Verify HTTP job-admission backpressure without invoking LLM or large corpora."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_platform.beta6 import Beta6JobManager
from shared_platform.products import ProductProfile
from shared_platform.queue_worker import Beta6DurableQueueWorker
from shared_platform.server import create_app


SESSION_TOKEN = "admission-load-session-token-abcdefghijklmnopqrstuvwxyz"
DEFAULT_MAX_P95_MS = 2000


def _env_override(values: dict[str, str]):
    class EnvGuard:
        def __enter__(self):
            self.previous = {key: os.environ.get(key) for key in values}
            os.environ.update(values)
            return self

        def __exit__(self, exc_type, exc, tb):
            for key, value in self.previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    return EnvGuard()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _rss_bytes() -> int:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        rss_pages = int(Path("/proc/self/statm").read_text(encoding="utf-8").split()[1])
        return int(rss_pages * page_size)
    except Exception:
        return 0


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((percentile / 100.0) * len(ordered)) - 1))
    return int(ordered[index])


def _make_profile(db_path: Path) -> ProductProfile:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()
    return ProductProfile(
        key="islam",
        name="Admission Load Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="load verifier",
    )


def _build_blocking_app(
    *,
    runs_root: Path,
    max_workers: int,
    max_pending_jobs: int,
    retry_after_seconds: int,
    durable_queue_only: bool = False,
) -> tuple[Any, Beta6JobManager, threading.Event]:
    release = threading.Event()
    profile = _make_profile(runs_root.parent / "admission-load.sqlite3")
    with _env_override(
        {
            "RELIGION_LLM_DISABLED": "1",
            "RELIGION_QUEUE_RETRY_AFTER_SECONDS": str(retry_after_seconds),
            "RELIGION_RESUME_PENDING_JOBS": "0",
        }
    ):
        runtime = Beta6JobManager(
            {"islam": profile},
            runs_root=runs_root,
            max_workers=max_workers,
            max_pending_jobs=max_pending_jobs,
            resume_pending_jobs=False,
            local_execution_enabled=not durable_queue_only,
        )

    def blocking_run_context(context):
        runtime._set_progress(context, "candidate_search", message="admission load hold")
        release.wait(timeout=30)
        runtime._set_and_persist_status(
            context,
            runtime._status_payload(context, status="completed", stage="completed", selected_count=0),
        )
        return {}

    runtime._run_context = blocking_run_context  # type: ignore[method-assign]
    app = create_app({"islam": profile}, runtime=runtime, rate_limit_per_minute=0)
    return app, runtime, release


def _start_server(app: Any, port: int):
    import uvicorn

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="admission-load-uvicorn", daemon=True)
    thread.start()
    deadline = time.time() + 10
    health_url = f"http://127.0.0.1:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=0.2) as response:
                if response.status == 200:
                    return server, thread
        except Exception:
            time.sleep(0.05)
    server.should_exit = True
    thread.join(timeout=2)
    raise RuntimeError("temporary admission-load server did not start")


def _submit_job(base_url: str, index: int, timeout_seconds: float = 10.0) -> dict[str, Any]:
    body = json.dumps({"query": f"admission load query {index}", "language": "en"}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/islam/jobs",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Beta6-Session-Token": SESSION_TOKEN,
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = int(response.status)
            headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        status = int(error.code)
        headers = {key.lower(): value for key, value in error.headers.items()}
    except Exception as exc:  # noqa: BLE001 - verifier reports failure as data.
        return {
            "index": index,
            "status": 0,
            "elapsedMs": int(round((time.perf_counter() - started) * 1000)),
            "error": str(exc),
            "body": {},
            "headers": {},
        }
    return {
        "index": index,
        "status": status,
        "elapsedMs": int(round((time.perf_counter() - started) * 1000)),
        "error": "",
        "body": payload,
        "headers": headers,
    }


def _structured_rejection(item: dict[str, Any], retry_after_seconds: int) -> bool:
    if item.get("status") != 503:
        return False
    detail = (item.get("body") or {}).get("detail") or {}
    capacity = detail.get("capacity") or {}
    return (
        detail.get("code") == "beta6_queue_full"
        and detail.get("retryAfterSeconds") == retry_after_seconds
        and str(item.get("headers", {}).get("retry-after") or "") == str(retry_after_seconds)
        and capacity.get("saturated") is True
    )


def _artifact_counts(runs_root: Path, accepted: int) -> dict[str, int]:
    job_run_dirs = [path for path in runs_root.iterdir() if path.is_dir() and path.name != "_beta6_queue"] if runs_root.exists() else []
    queue_rows = list((runs_root / "_beta6_queue").glob("*.json")) if (runs_root / "_beta6_queue").exists() else []
    durable_queue_only_rows = 0
    for row_path in queue_rows:
        try:
            row = json.loads(row_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if row.get("executionMode") == "durable_queue_only" and row.get("status") == "queued":
            durable_queue_only_rows += 1
    return {
        "jobRunDirs": len(job_run_dirs),
        "queueRows": len(queue_rows),
        "durableQueueOnlyRows": durable_queue_only_rows,
        "rejectedJobArtifacts": max(0, len(job_run_dirs) - int(accepted)),
    }


def _queue_status_counts(runs_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    queue_root = runs_root / "_beta6_queue"
    for row_path in queue_root.glob("*.json") if queue_root.exists() else []:
        try:
            row = json.loads(row_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(row.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _drain_with_external_worker(
    *,
    source_runtime: Beta6JobManager,
    runs_root: Path,
    accepted: int,
    worker_count: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    if accepted <= 0:
        return {
            "enabled": True,
            "resumed": 0,
            "completed": 0,
            "queueRowsCompleted": 0,
            "statusCounts": _queue_status_counts(runs_root),
        }
    worker_runtime = Beta6JobManager(
        source_runtime._profiles,  # type: ignore[attr-defined]
        runs_root=runs_root,
        max_workers=max(1, int(worker_count or 1)),
        max_pending_jobs=max(accepted, int(worker_count or 1)),
        resume_pending_jobs=False,
    )

    def fast_run_context(context):
        result = {
            "jobId": context.job_id,
            "product": context.product.key,
            "query": context.query,
            "answer": "durable queue worker drain proof",
            "beta6": {"analysisMode": "beta6", "workerDrainProof": True},
        }
        (context.run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        worker_runtime._set_and_persist_status(
            context,
            worker_runtime._status_payload(context, status="completed", stage="completed", selected_count=0),
        )
        return result

    worker_runtime._run_context = fast_run_context  # type: ignore[method-assign]
    worker = Beta6DurableQueueWorker(worker_runtime, batch_limit=accepted, poll_interval_seconds=0.01)
    started = time.perf_counter()
    try:
        report = worker.run_once()
        deadline = time.perf_counter() + max(0.1, float(timeout_seconds or 1.0))
        completed = 0
        while time.perf_counter() < deadline:
            counts = _queue_status_counts(runs_root)
            completed = int(counts.get("completed") or 0)
            if completed >= accepted:
                break
            time.sleep(0.02)
        worker_runtime.shutdown(wait=True, cancel_futures=False)
        counts = _queue_status_counts(runs_root)
        completed = int(counts.get("completed") or 0)
        result_files = len(list(runs_root.glob("job-*/result.json")))
        return {
            "enabled": True,
            "resumed": int(report.get("resumed") or 0),
            "completed": min(completed, result_files),
            "queueRowsCompleted": completed,
            "resultFiles": result_files,
            "statusCounts": counts,
            "wallClockMs": int(round((time.perf_counter() - started) * 1000)),
            "workers": max(1, int(worker_count or 1)),
        }
    finally:
        worker_runtime.shutdown(wait=False, cancel_futures=True)


def _dry_report(
    *,
    requests: int,
    concurrency: int,
    max_workers: int,
    max_pending_jobs: int,
    retry_after_seconds: int,
    max_p95_ms: int,
    durable_queue_only: bool = False,
    drain_with_worker: bool = False,
    worker_count: int = 2,
    drain_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    accepted = min(requests, max_pending_jobs)
    rejected = max(0, requests - accepted)
    return {
        "passes": True,
        "dryRun": True,
        "mode": "durable_queue_only" if durable_queue_only else "blocking_local_execution",
        "safety": {
            "llmDisabled": True,
            "usesTemporaryCorpus": True,
            "doesNotCallConfiguredSplitApps": True,
            "localExecutorSubmissionDisabled": bool(durable_queue_only),
            "workerDrainEnabled": bool(drain_with_worker),
        },
        "requests": {
            "total": requests,
            "concurrency": concurrency,
            "accepted": 0,
            "rejected": 0,
            "unexpected": 0,
        },
        "expected": {
            "acceptedAtMost": accepted,
            "structured503AtLeast": rejected,
        },
        "capacity": {
            "maxWorkers": max_workers,
            "maxPendingJobs": max_pending_jobs,
            "retryAfterSeconds": retry_after_seconds,
            "saturatedDuringLoad": bool(rejected),
        },
        "latency": {"maxP95Ms": max_p95_ms},
        "workerDrain": {
            "enabled": bool(drain_with_worker),
            "resumed": 0,
            "completed": 0,
            "queueRowsCompleted": 0,
        },
    }


def build_report(
    *,
    requests: int = 256,
    concurrency: int = 32,
    max_workers: int = 2,
    max_pending_jobs: int = 32,
    retry_after_seconds: int = 30,
    max_p95_ms: int = DEFAULT_MAX_P95_MS,
    runs_root: Path | None = None,
    dry_run: bool = False,
    durable_queue_only: bool = False,
    drain_with_worker: bool = False,
    worker_count: int = 2,
    drain_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    requests = max(1, int(requests))
    concurrency = max(1, min(int(concurrency), requests))
    max_workers = max(1, int(max_workers))
    max_pending_jobs = max(1, int(max_pending_jobs))
    retry_after_seconds = max(0, int(retry_after_seconds))
    max_p95_ms = max(1, int(max_p95_ms))
    if dry_run:
        return _dry_report(
            requests=requests,
            concurrency=concurrency,
            max_workers=max_workers,
            max_pending_jobs=max_pending_jobs,
            retry_after_seconds=retry_after_seconds,
            max_p95_ms=max_p95_ms,
            durable_queue_only=durable_queue_only,
            drain_with_worker=drain_with_worker,
            worker_count=worker_count,
            drain_timeout_seconds=drain_timeout_seconds,
        )

    temp_dir = None
    if runs_root is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="beta6-admission-load-")
        runs_root = Path(temp_dir.name) / "runs"
    runs_root = Path(runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    app, runtime, release = _build_blocking_app(
        runs_root=runs_root,
        max_workers=max_workers,
        max_pending_jobs=max_pending_jobs,
        retry_after_seconds=retry_after_seconds,
        durable_queue_only=durable_queue_only,
    )
    port = _free_port()
    server = None
    thread = None
    rss_before = _rss_bytes()
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    capacity_during: dict[str, Any] = {}
    artifacts: dict[str, int] = {}
    worker_drain_report: dict[str, Any] = {
        "enabled": bool(drain_with_worker),
        "resumed": 0,
        "completed": 0,
        "queueRowsCompleted": 0,
    }
    try:
        server, thread = _start_server(app, port)
        base_url = f"http://127.0.0.1:{port}"
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_submit_job, base_url, index) for index in range(requests)]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        capacity_during = runtime.capacity_snapshot()
        accepted_so_far = sum(1 for item in results if item.get("status") == 200)
        if drain_with_worker:
            worker_drain_report = _drain_with_external_worker(
                source_runtime=runtime,
                runs_root=runs_root,
                accepted=accepted_so_far,
                worker_count=worker_count,
                timeout_seconds=drain_timeout_seconds,
            )
    finally:
        release.set()
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5)
        runtime._executor.shutdown(wait=True, cancel_futures=True)

    elapsed = int(round((time.perf_counter() - started) * 1000))
    rss_after = _rss_bytes()
    accepted_items = [item for item in results if item.get("status") == 200]
    rejected_items = [item for item in results if item.get("status") == 503]
    unexpected_items = [item for item in results if item.get("status") not in {200, 503}]
    accepted = len(accepted_items)
    rejected = len(rejected_items)
    latencies = [int(item.get("elapsedMs") or 0) for item in results]
    p95 = _percentile(latencies, 95)
    all_rejected_structured = all(_structured_rejection(item, retry_after_seconds) for item in rejected_items)
    artifacts = _artifact_counts(runs_root, accepted)
    if temp_dir is not None:
        temp_dir.cleanup()
    expected_accepted = min(requests, max_pending_jobs)
    expected_rejected = max(0, requests - expected_accepted)
    passes = (
        accepted == expected_accepted
        and rejected == expected_rejected
        and not unexpected_items
        and all_rejected_structured
        and artifacts["rejectedJobArtifacts"] == 0
        and p95 <= max_p95_ms
        and (
            not drain_with_worker
            or (
                worker_drain_report.get("resumed") == accepted
                and worker_drain_report.get("completed") == accepted
                and worker_drain_report.get("queueRowsCompleted") == accepted
            )
        )
    )
    return {
        "passes": passes,
        "dryRun": False,
        "mode": "durable_queue_only" if durable_queue_only else "blocking_local_execution",
        "safety": {
            "llmDisabled": True,
            "usesTemporaryCorpus": True,
            "doesNotCallConfiguredSplitApps": True,
            "localExecutorSubmissionDisabled": bool(durable_queue_only),
            "workerDrainEnabled": bool(drain_with_worker),
        },
        "requests": {
            "total": requests,
            "concurrency": concurrency,
            "accepted": accepted,
            "rejected": rejected,
            "unexpected": len(unexpected_items),
        },
        "expected": {
            "acceptedAtMost": expected_accepted,
            "structured503AtLeast": expected_rejected,
        },
        "backpressure": {
            "allRejectedStructured": all_rejected_structured,
            "retryAfterSeconds": retry_after_seconds,
        },
        "capacity": {
            **capacity_during,
            "saturatedDuringLoad": bool(capacity_during.get("saturated")) or rejected > 0,
        },
        "latency": {
            "p50Ms": _percentile(latencies, 50),
            "p95Ms": p95,
            "maxMs": max(latencies) if latencies else 0,
            "maxP95Ms": max_p95_ms,
            "wallClockMs": elapsed,
        },
        "memory": {
            "rssBeforeBytes": rss_before,
            "rssAfterBytes": rss_after,
            "rssDeltaBytes": int(rss_after - rss_before) if rss_before and rss_after else 0,
        },
        "artifacts": artifacts,
        "workerDrain": worker_drain_report,
        "sampleAccepted": accepted_items[:3],
        "sampleRejected": rejected_items[:3],
        "unexpectedResponses": unexpected_items[:5],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON report")
    parser.add_argument("--output", help="write JSON report to this path")
    parser.add_argument("--dry-run", action="store_true", help="emit the safe-load contract without starting HTTP server")
    parser.add_argument("--requests", type=int, default=256)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--max-pending-jobs", type=int, default=32)
    parser.add_argument("--retry-after-seconds", type=int, default=30)
    parser.add_argument("--max-p95-ms", type=int, default=DEFAULT_MAX_P95_MS)
    parser.add_argument("--runs-root", type=Path, help="optional temporary runs root to inspect after run")
    parser.add_argument(
        "--durable-queue-only",
        action="store_true",
        help="accept jobs into durable queue without submitting local executor futures",
    )
    parser.add_argument("--drain-with-worker", action="store_true", help="run a fast external worker drain after admission")
    parser.add_argument("--worker-count", type=int, default=2, help="workers for --drain-with-worker")
    parser.add_argument("--drain-timeout-seconds", type=float, default=10.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        requests=args.requests,
        concurrency=args.concurrency,
        max_workers=args.max_workers,
        max_pending_jobs=args.max_pending_jobs,
        retry_after_seconds=args.retry_after_seconds,
        max_p95_ms=args.max_p95_ms,
        runs_root=args.runs_root,
        dry_run=args.dry_run,
        durable_queue_only=args.durable_queue_only,
        drain_with_worker=args.drain_with_worker,
        worker_count=args.worker_count,
        drain_timeout_seconds=args.drain_timeout_seconds,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        state = "PASS" if report["passes"] else "FAIL"
        print(f"{state} admission load")
        print(
            f"requests={report['requests']['total']} accepted={report['requests']['accepted']} "
            f"rejected={report['requests']['rejected']} p95={report.get('latency', {}).get('p95Ms', 0)}ms"
        )
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
