from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from threading import Event
from typing import Any, Callable, Iterable

from .beta6 import Beta6JobManager
from .products import PRODUCT_PROFILES, ProductProfile


SleepFunc = Callable[[float], Any]


class Beta6DurableQueueWorker:
    """Small durable-queue worker loop around Beta6JobManager.

    The durable queue claim lease still lives in Beta6JobManager. This class is
    only the operational loop an external process can run repeatedly.
    """

    def __init__(
        self,
        runtime: Beta6JobManager,
        *,
        batch_limit: int = 8,
        poll_interval_seconds: float = 1.0,
        sleep_func: SleepFunc = time.sleep,
    ) -> None:
        self.runtime = runtime
        self.batch_limit = max(0, int(batch_limit))
        self.poll_interval_seconds = max(0.01, float(poll_interval_seconds))
        self._sleep = sleep_func

    def run_once(self) -> dict[str, Any]:
        resumed = int(self.runtime.resume_durable_queue_once(limit=self.batch_limit))
        return {"iterations": 1, "resumed": resumed, "slept": False}

    def run_forever(self, *, stop_event: Event | None = None, max_iterations: int | None = None) -> dict[str, Any]:
        stop = stop_event or Event()
        iterations = 0
        resumed_total = 0
        sleeps = 0
        iteration_limit = None if max_iterations is None else max(0, int(max_iterations))
        while not stop.is_set():
            if iteration_limit is not None and iterations >= iteration_limit:
                break
            report = self.run_once()
            iterations += 1
            resumed = int(report.get("resumed") or 0)
            resumed_total += resumed
            can_continue = iteration_limit is None or iterations < iteration_limit
            if resumed <= 0 and can_continue and not stop.is_set():
                self._sleep(self.poll_interval_seconds)
                sleeps += 1
        return {"iterations": iterations, "resumed": resumed_total, "sleeps": sleeps}


def build_worker_runtime(
    *,
    product_keys: Iterable[str] | None = None,
    runs_root: Path | str | None = None,
    max_workers: int | None = None,
    max_pending_jobs: int | None = None,
) -> Beta6JobManager:
    profiles = _profiles_for(product_keys)
    kwargs: dict[str, Any] = {"resume_pending_jobs": False}
    if runs_root is not None:
        kwargs["runs_root"] = Path(runs_root)
    if max_workers is not None:
        kwargs["max_workers"] = int(max_workers)
    if max_pending_jobs is not None:
        kwargs["max_pending_jobs"] = int(max_pending_jobs)
    return Beta6JobManager(profiles, **kwargs)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    product_keys = _normalize_product_keys(args.product)
    runtime = build_worker_runtime(
        product_keys=product_keys,
        runs_root=Path(args.runs_root) if args.runs_root else None,
        max_workers=args.max_workers,
        max_pending_jobs=args.max_pending_jobs,
    )
    worker = Beta6DurableQueueWorker(
        runtime,
        batch_limit=args.limit,
        poll_interval_seconds=args.poll_interval,
    )
    if args.once:
        report = {"mode": "once", "products": product_keys, **worker.run_once()}
    else:
        report = {
            "mode": "forever",
            "products": product_keys,
            **worker.run_forever(max_iterations=args.max_iterations),
        }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a beta6 durable queue worker.")
    parser.add_argument(
        "--product",
        action="append",
        default=[],
        help="Product key to serve. Repeat for multiple products. Defaults to all products.",
    )
    parser.add_argument("--once", action="store_true", help="Claim one batch and exit.")
    parser.add_argument(
        "--limit",
        type=int,
        default=_env_int("RELIGION_QUEUE_WORKER_BATCH_LIMIT", 8),
        help="Durable jobs to claim per iteration.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=_env_float("RELIGION_QUEUE_WORKER_POLL_SECONDS", 1.0),
        help="Seconds to sleep after an idle iteration.",
    )
    parser.add_argument("--max-iterations", type=int, default=None, help="Test/one-shot loop cap.")
    parser.add_argument("--runs-root", default="", help="Optional runs root override.")
    parser.add_argument("--max-workers", type=int, default=None, help="Runtime worker override.")
    parser.add_argument("--max-pending-jobs", type=int, default=None, help="Runtime pending-job override.")
    return parser


def _profiles_for(product_keys: Iterable[str] | None) -> dict[str, ProductProfile]:
    keys = _normalize_product_keys(product_keys)
    profiles: dict[str, ProductProfile] = {}
    for key in keys:
        try:
            profiles[key] = PRODUCT_PROFILES[key]
        except KeyError as exc:
            raise ValueError(f"unknown product: {key}") from exc
    return profiles


def _normalize_product_keys(product_keys: Iterable[str] | None) -> list[str]:
    raw_keys = list(product_keys or [])
    keys = [str(key or "").strip().lower() for key in raw_keys if str(key or "").strip()]
    if not keys:
        keys = sorted(PRODUCT_PROFILES)
    unique: list[str] = []
    for key in keys:
        if key not in unique:
            unique.append(key)
    for key in unique:
        if key not in PRODUCT_PROFILES:
            raise ValueError(f"unknown product: {key}")
    return unique


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
