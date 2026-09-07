"""Safely run one model-authored probe against immutable A/B modules."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
SCHEMA_VERSION = 1
DEFAULT_CONTEXT = Path("/opt/paired/context.json")
MASKED_ROOTS = ("/home", "/root", "/mnt", "/tmp", "/var/tmp")
def _sha(payload: bytes) -> str: return hashlib.sha256(payload).hexdigest()
def _file(value, label: str, parent: Path | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute() and parent is not None:
        path = parent / path
    resolved = path.resolve(strict=True)
    if path.is_symlink() or not resolved.is_file():
        raise ValueError(f"{label} must be a non-symlink regular file")
    if parent is not None:
        try:
            resolved.relative_to(Path(parent).resolve())
        except ValueError as exc:
            raise ValueError(f"{label} escapes staged directory") from exc
    return resolved
def _context(path: Path) -> dict:
    path = _file(path, "context")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("context must be an object")
    root = path.parent
    a, b = data.get("sourceA"), data.get("sourceB")
    ha, hb = data.get("sourceSha256A"), data.get("sourceSha256B")
    if not all(isinstance(x, str) for x in (a, b, ha, hb)):
        raise ValueError("context needs sourceA/sourceB and source SHA-256 values")
    out = {"sourceA": _file(a, "sourceA", root), "sourceB": _file(b, "sourceB", root),
           "expectedA": ha, "expectedB": hb,
           "python": str(data.get("python", sys.executable)),
           "pythonBase": data.get("pythonBase"), "venv": data.get("venv"),
           "nltkData": data.get("nltkData"), "timeout": float(data.get("timeoutSeconds", 8)),
           "contextPath": path}
    if not 0 < out["timeout"] <= 30:
        raise ValueError("probe timeout must be in (0, 30] seconds")
    for key in ("pythonBase", "venv", "nltkData"):
        if out[key] is not None:
            out[key] = str(Path(out[key]).resolve(strict=True))
    if _sha(out["sourceA"].read_bytes()) != ha or _sha(out["sourceB"].read_bytes()) != hb:
        raise ValueError("candidate source hash does not match immutable context")
    return out
def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise
    return module
def _child(args) -> int:
    candidate, probe = Path(args.candidate), Path(args.probe)
    seen: list[str] = []
    stdout, stderr = io.StringIO(), io.StringIO()
    value, error = None, None
    started = time.monotonic()
    def trace(frame, event, _arg):
        if event == "call" and Path(frame.f_code.co_filename).resolve() == candidate.resolve():
            name = frame.f_code.co_name
            if name != "<module>" and name not in seen:
                seen.append(name)
        return trace
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            module = _load(candidate, "paired_candidate")
            probe_module = _load(probe, "paired_probe")
            fn = getattr(probe_module, "probe")
            if not callable(fn):
                raise TypeError("probe.py must define callable probe(candidate)")
            sys.settrace(trace)
            try:
                value = json.loads(json.dumps(fn(module), ensure_ascii=False))
            finally:
                sys.settrace(None)
    except BaseException as exc:  # candidate/probe failure is returned as evidence
        sys.settrace(None)
        error = {"type": type(exc).__name__, "message": str(exc)[:2000]}
    print(json.dumps({
        "schemaVersion": SCHEMA_VERSION, "candidate": args.label,
        "sourceSha256": args.source_sha, "probeSHA256": args.probe_sha,
        "output": value, "exception": error, "visitedMethods": seen,
        "stdout": stdout.getvalue()[:8000], "stderr": stderr.getvalue()[:8000],
        "durationSeconds": time.monotonic() - started, "pid": os.getpid(),
    }, ensure_ascii=False, sort_keys=True), flush=True)
    return 0
def _command(ctx: dict, source: Path, probe: Path, work: Path,
             source_sha: str, probe_sha: str, label: str) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise FileNotFoundError("bubblewrap is required for paired probes")
    python = ctx["python"]
    command = [bwrap, "--die-with-parent", "--new-session", "--unshare-all", "--ro-bind", "/", "/"]
    for root in MASKED_ROOTS:
        command += ["--tmpfs", root]
    for host, target in ((ctx.get("pythonBase"), ctx.get("pythonBase")), (ctx.get("venv"), ctx.get("venv")), (ctx.get("nltkData"), "/tmp/nltk-data")):
        if host:
            command += ["--ro-bind", str(host), str(target)]
    command += ["--dir", "/tmp/pair-work", "--bind", str(work), "/tmp/pair-work",
                "--ro-bind", str(source), "/tmp/pair-candidate.py",
                "--ro-bind", str(probe), "/tmp/pair-probe.py",
                "--ro-bind", str(Path(__file__).resolve()), "/tmp/pair-helper.py",
                "--proc", "/proc", "--dev", "/dev", "--clearenv",
                "--dir", "/tmp/home", "--setenv", "HOME", "/tmp/home"]
    if ctx.get("nltkData"):
        command += ["--setenv", "NLTK_DATA", "/tmp/nltk-data"]
    command += ["--setenv", "PATH", f"{Path(python).parent}:/usr/bin:/bin",
                "--setenv", "PYTHONPATH", "", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--setenv", "LANG", "C.UTF-8", "--chdir", "/tmp/pair-work",
                str(python), "/tmp/pair-helper.py", "--child",
                "--candidate", "/tmp/pair-candidate.py", "--probe", "/tmp/pair-probe.py",
                "--label", label, "--source-sha", source_sha, "--probe-sha", probe_sha]
    return command
def _run_one(ctx: dict, source: Path, label: str, probe: Path, probe_sha: str) -> dict:
    source_sha = _sha(source.read_bytes())
    with tempfile.TemporaryDirectory(prefix="classeval-paired-probe-") as temp:
        command = _command(ctx, source, probe, Path(temp), source_sha, probe_sha, label)
        started = time.monotonic()
        try:
            done = subprocess.run(command, text=True, capture_output=True,
                                  timeout=ctx["timeout"], check=False)
        except subprocess.TimeoutExpired:
            return {"candidate": label, "sourceSha256": source_sha, "probeSHA256": probe_sha,
                    "output": None, "exception": {"type": "TimeoutError", "message": "hard timeout"},
                    "visitedMethods": [], "stdout": "", "stderr": "",
                    "durationSeconds": time.monotonic() - started}
    try:
        if done.returncode != 0:
            raise ValueError(f"child exited with code {done.returncode}")
        record = json.loads([line for line in done.stdout.splitlines() if line.strip()][-1])
        required = ("schemaVersion", "candidate", "sourceSha256", "probeSHA256", "output", "exception", "visitedMethods", "stdout", "stderr", "durationSeconds")
        if (not isinstance(record, dict) or any(key not in record for key in required)
                or record["schemaVersion"] != SCHEMA_VERSION
                or record["candidate"] != label
                or record["sourceSha256"] != source_sha
                or record["probeSHA256"] != probe_sha
                or not isinstance(record["visitedMethods"], list)
                or not all(isinstance(item, str) for item in record["visitedMethods"])
                or record["exception"] is not None and not isinstance(record["exception"], dict)
                or not isinstance(record["stdout"], str)
                or not isinstance(record["stderr"], str)
                or not isinstance(record["durationSeconds"], (int, float))):
            raise ValueError("child metadata/schema mismatch")
        return record
    except (AttributeError, IndexError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return {"candidate": label, "sourceSha256": source_sha, "probeSHA256": probe_sha, "output": None, "exception": {"type": type(exc).__name__, "message": str(exc)[:2000]}, "visitedMethods": [], "stdout": done.stdout[-8000:], "stderr": done.stderr[-8000:], "exitCode": done.returncode, "durationSeconds": time.monotonic() - started}
def _pair(args) -> int:
    ctx = _context(Path(args.context))
    probe = _file(args.probe, "probe")
    probe_bytes = probe.read_bytes()
    probe_sha = _sha(probe_bytes)
    compile(probe_bytes, str(probe), "exec")
    with tempfile.TemporaryDirectory(prefix="classeval-paired-probe-input-") as temp:
        snapshot = Path(temp) / "probe.py"
        snapshot.write_bytes(probe_bytes)
        snapshot.chmod(0o444)
        result = {"schemaVersion": SCHEMA_VERSION, "probeSHA256": probe_sha,
                  "sourceSHA256A": ctx["expectedA"], "sourceSHA256B": ctx["expectedB"],
                  "contextPath": str(ctx["contextPath"]), "probePath": str(probe),
                  "candidates": {"A": _run_one(ctx, ctx["sourceA"], "A", snapshot, probe_sha),
                                 "B": _run_one(ctx, ctx["sourceB"], "B", snapshot, probe_sha)},
                  "separateProcesses": True, "timeoutSeconds": ctx["timeout"]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0
def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--candidate")
    parser.add_argument("--label")
    parser.add_argument("--source-sha")
    parser.add_argument("--probe-sha")
    args = parser.parse_args(argv)
    if args.child:
        if not all((args.candidate, args.probe, args.label, args.source_sha, args.probe_sha)): parser.error("incomplete child arguments")
        return _child(args)
    if args.probe is None:
        parser.error("--probe is required")
    return _pair(args)
if __name__ == "__main__":
    raise SystemExit(main())
