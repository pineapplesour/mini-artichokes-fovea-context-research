import json
from pathlib import Path

import pytest

from shared_platform.products import ProductProfile


class FakeRuntime:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def resume_durable_queue_once(self, *, limit=None):
        self.calls.append({"limit": limit})
        if self.results:
            return self.results.pop(0)
        return 0


def test_beta6_queue_worker_run_once_uses_resume_primitive_limit():
    from shared_platform.queue_worker import Beta6DurableQueueWorker

    runtime = FakeRuntime([2])
    worker = Beta6DurableQueueWorker(runtime, batch_limit=7, poll_interval_seconds=0.01)

    report = worker.run_once()

    assert report == {"iterations": 1, "resumed": 2, "slept": False}
    assert runtime.calls == [{"limit": 7}]


def test_beta6_queue_worker_loop_sleeps_only_when_no_jobs_are_resumed():
    from shared_platform.queue_worker import Beta6DurableQueueWorker

    runtime = FakeRuntime([0, 3])
    sleeps = []
    worker = Beta6DurableQueueWorker(
        runtime,
        batch_limit=5,
        poll_interval_seconds=0.25,
        sleep_func=sleeps.append,
    )

    report = worker.run_forever(max_iterations=2)

    assert report == {"iterations": 2, "resumed": 3, "sleeps": 1}
    assert runtime.calls == [{"limit": 5}, {"limit": 5}]
    assert sleeps == [0.25]


def test_beta6_queue_worker_runtime_factory_disables_startup_resume(monkeypatch, tmp_path):
    from shared_platform import queue_worker

    captured = {}

    class CapturingJobManager:
        def __init__(self, profiles, **kwargs):
            captured["profiles"] = profiles
            captured["kwargs"] = kwargs

    profile = ProductProfile(
        key="islam",
        name="Islam",
        db_path=tmp_path / "islam.sqlite3",
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="safe",
    )
    monkeypatch.setattr(queue_worker, "PRODUCT_PROFILES", {"islam": profile})
    monkeypatch.setattr(queue_worker, "Beta6JobManager", CapturingJobManager)

    runtime = queue_worker.build_worker_runtime(product_keys=["islam"], runs_root=tmp_path / "runs")

    assert isinstance(runtime, CapturingJobManager)
    assert captured["profiles"] == {"islam": profile}
    assert captured["kwargs"]["resume_pending_jobs"] is False
    assert captured["kwargs"]["runs_root"] == tmp_path / "runs"


def test_beta6_queue_worker_cli_once_prints_json(monkeypatch, capsys):
    from shared_platform import queue_worker

    class Runtime:
        def resume_durable_queue_once(self, *, limit=None):
            assert limit == 4
            return 6

    monkeypatch.setattr(queue_worker, "build_worker_runtime", lambda **kwargs: Runtime())

    exit_code = queue_worker.main(["--once", "--limit", "4", "--product", "islam"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "mode": "once",
        "products": ["islam"],
        "iterations": 1,
        "resumed": 6,
        "slept": False,
    }


def test_beta6_queue_worker_rejects_unknown_product():
    from shared_platform.queue_worker import build_worker_runtime

    with pytest.raises(ValueError, match="unknown product"):
        build_worker_runtime(product_keys=["missing"])


def test_beta6_queue_worker_tool_wrapper_delegates_to_module_main():
    wrapper = Path("tools/run_beta6_queue_worker.py")

    assert wrapper.exists()
    text = wrapper.read_text(encoding="utf-8")
    assert "shared_platform.queue_worker" in text
    assert "queue_worker.main()" in text
