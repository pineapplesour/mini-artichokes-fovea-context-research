#!/usr/bin/env python3
"""Portable fallback runner for constrained local maintenance.

The normal workflow is still branch, pull request, review, and local verification.
This script is the constrained-environment path: a contributor can apply a
unified diff to a downloaded repository, checkpoint it, wire DB/env vars, run
contract checks, and open one product server.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DB_ENV = {
    "islam": "RELIGION_ISLAM_DB_PATH",
    "tcm": "RELIGION_TCM_DB_PATH",
    "simli": "RELIGION_SIMLI_DB_PATH",
    "lawkey": "RELIGION_LAWKEY_DB_PATH",
}
EXTERNAL_PRODUCTS = {
    "lawkey": {
        "port": 8037,
        "landing": "/",
        "chat": "/",
        "db": "/var/lib/universal-artichoke/lawkey/precedents.sqlite3",
    }
}
REQUIRED_RUNTIME_MODULES = ("fastapi", "uvicorn", "pydantic")
_METADATA_CACHE: dict[Path, dict[str, Any]] = {}


class StandaloneError(RuntimeError):
    pass


def detect_project_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not (root / "apps/product_app.py").exists():
            raise StandaloneError(f"--project-dir is not a platform root: {root}")
        return root
    if (REPO_ROOT / "apps/product_app.py").exists():
        return REPO_ROOT
    raise StandaloneError("could not find apps/product_app.py in the repository root")


def product_module(product: str, *, project_root: Path | None = None) -> str:
    key = _normalize_product(product, project_root=project_root)
    return f"apps.{key}.server:app"


def product_urls(product: str, *, host: str, port: int, project_root: Path | None = None) -> dict[str, str]:
    key = _normalize_product(product, project_root=project_root)
    metadata = _load_metadata(project_root)
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    base = f"http://{browser_host}:{int(port)}"
    return {
        "health": f"{base}/api/health",
        "landing": f"{base}{metadata['landing_routes'][key]}",
        "chat": f"{base}{metadata['chat_routes'][key]}",
    }


def parse_diff_paths(diff_path: Path) -> set[Path]:
    paths: set[Path] = set()
    text = diff_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if not (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        raw = line[4:].strip()
        token = raw.split("\t", 1)[0].split(" ", 1)[0]
        if token == "/dev/null":
            continue
        if token.startswith("a/") or token.startswith("b/"):
            token = token[2:]
        path = Path(token)
        _assert_safe_relative_path(path)
        paths.add(path)
    return paths


def resolve_product_db(
    product: str,
    db_path: Path | None,
    env: dict[str, str],
    *,
    project_root: Path | None = None,
    allow_missing_db: bool,
) -> Path:
    key = _normalize_product(product, project_root=project_root)
    env_name = PRODUCT_DB_ENV[key]
    if db_path is not None:
        resolved = db_path.expanduser().resolve()
        env[env_name] = str(resolved)
    elif env.get(env_name):
        resolved = Path(env[env_name]).expanduser().resolve()
        env[env_name] = str(resolved)
    else:
        metadata = _load_metadata(project_root)
        external_db = metadata.get("db_paths", {}).get(key)
        resolved = Path(external_db).expanduser().resolve() if external_db else metadata["get_product"](key).db_path.expanduser().resolve()
        env[env_name] = str(resolved)

    if not resolved.exists() and not allow_missing_db:
        raise StandaloneError(
            f"{key} database is missing: {resolved}\n"
            f"Pass --db /path/to/{key}.sqlite3 or set {env_name}. "
            "Small fixture DBs are included for islam/tcm/simli; full DB releases are described in db/DB_SHARING_GUIDE.md."
        )
    return resolved


def apply_diff_if_requested(diff_path: Path | None, *, project_root: Path) -> Path | None:
    if diff_path is None:
        return None
    resolved_diff = diff_path.expanduser().resolve()
    if not resolved_diff.exists():
        raise StandaloneError(f"diff file does not exist: {resolved_diff}")
    paths = parse_diff_paths(resolved_diff)
    if not paths:
        raise StandaloneError(f"diff has no file paths: {resolved_diff}")

    method, apply_root = _choose_diff_apply_method(resolved_diff, paths, project_root=project_root)
    checkpoint = create_checkpoint(apply_root, resolved_diff, paths)
    print(f"[standalone] checkpoint: {checkpoint}")

    if method == "git":
        _run([_git_executable(), "apply", str(resolved_diff)], cwd=apply_root)
    elif method == "patch":
        _run([_patch_executable(), "-p1", "-i", str(resolved_diff)], cwd=apply_root)
    else:
        raise StandaloneError(f"unsupported diff apply method: {method}")
    print(f"[standalone] diff applied with {method} from {apply_root}")
    return checkpoint


def create_checkpoint(apply_root: Path, diff_path: Path, diff_paths: Iterable[Path]) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    checkpoint = REPO_ROOT / "standalone_checkpoints" / f"{stamp}-before-diff"
    files_root = checkpoint / "files"
    files_root.mkdir(parents=True, exist_ok=False)
    shutil.copy2(diff_path, checkpoint / "change.patch")

    entries: list[dict[str, str]] = []
    for rel in sorted(diff_paths, key=lambda item: item.as_posix()):
        _assert_safe_relative_path(rel)
        source = (apply_root / rel).resolve()
        status = "missing"
        if source.exists() and source.is_file():
            status = "copied"
            target = files_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        entries.append({"path": rel.as_posix(), "status": status})

    manifest = {
        "createdAt": dt.datetime.now(dt.UTC).isoformat(),
        "applyRoot": str(apply_root),
        "diff": str(diff_path),
        "files": entries,
        "restore": "Copy files/* back to applyRoot, or use git checkout/revert if this is a git repository.",
    }
    (checkpoint / "CHECKPOINT.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return checkpoint


def install_dependencies_if_requested(install_deps: bool, *, project_root: Path) -> None:
    missing = [name for name in REQUIRED_RUNTIME_MODULES if importlib.util.find_spec(name) is None]
    if not missing:
        return
    if not install_deps:
        raise StandaloneError(
            "missing Python runtime dependencies: "
            + ", ".join(missing)
            + "\nRun again with --install-deps, or install requirements.txt manually."
        )
    _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=project_root)


def configure_llm_mode(mode: str, env: dict[str, str]) -> str:
    normalized = str(mode or "auto").strip().lower()
    if normalized not in {"auto", "disabled", "real"}:
        raise StandaloneError("--llm must be one of: auto, disabled, real")
    if normalized == "disabled":
        env["RELIGION_LLM_DISABLED"] = "1"
        env["RELIGION_LLM_PROVIDER"] = "disabled"
        return "disabled"
    if normalized == "real":
        env.pop("RELIGION_LLM_DISABLED", None)
        if env.get("RELIGION_LLM_PROVIDER") == "disabled":
            env.pop("RELIGION_LLM_PROVIDER", None)
        return "real"

    has_direct_provider = bool(env.get("RELIGION_CHAT_API_URL") or env.get("RELIGION_CHAT_API_KEY"))
    has_gemini_key = any(env.get(name) for name in ("RELIGION_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"))
    provider = env.get("RELIGION_LLM_PROVIDER", "").strip().lower()
    if has_direct_provider or has_gemini_key or provider in {"openai", "openai_compatible", "openai-compatible", "lawkey", "gemini"}:
        env.pop("RELIGION_LLM_DISABLED", None)
        return "real"
    env["RELIGION_LLM_DISABLED"] = "1"
    env["RELIGION_LLM_PROVIDER"] = "disabled"
    return "disabled"


def run_verification(skip_verify: bool, *, project_root: Path) -> None:
    if skip_verify:
        print("[standalone] verification skipped by --skip-verify")
        return
    commands = [
        [sys.executable, "tools/verify_repo_contracts.py"],
        [sys.executable, "tools/verify_app_parity.py", "--json"],
        [sys.executable, "tools/sync_native_shell_assets.py", "--check"],
    ]
    for command in commands:
        _run(command, cwd=project_root)


def run_server(args: argparse.Namespace, env: dict[str, str], *, project_root: Path) -> int:
    product = _normalize_product(args.product, project_root=project_root)
    metadata = _load_metadata(project_root)
    requested_port = int(args.port or metadata["ports"][product])
    port = requested_port if args.reuse_port or not _port_is_open(args.host, requested_port) else _find_free_port(requested_port + 1)
    if port != requested_port:
        print(f"[standalone] port {requested_port} is already in use; using {port}")

    urls = product_urls(product, host=args.host, port=port, project_root=project_root)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        product_module(product, project_root=project_root),
        "--host",
        args.host,
        "--port",
        str(port),
    ]
    print(f"[standalone] starting server: {' '.join(command)}")
    process = subprocess.Popen(command, cwd=project_root, env=env)
    try:
        wait_for_url(urls["health"], timeout_seconds=float(args.wait_seconds))
        if not args.skip_smoke:
            smoke_server(product, urls)
        print("[standalone] server URLs:")
        print(f"  landing: {urls['landing']}")
        print(f"  chat:    {urls['chat']}")
        if not args.no_open_browser:
            webbrowser.open(urls["landing"])
        if args.exit_after_smoke:
            return 0
        return process.wait()
    finally:
        if args.exit_after_smoke and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)


def wait_for_url(url: str, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if 200 <= response.status < 400:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.4)
    raise StandaloneError(f"server did not become healthy at {url}: {last_error}")


def smoke_server(product: str, urls: dict[str, str]) -> None:
    for name in ("health", "landing", "chat"):
        _get_ok(urls[name], label=name)
    base = urls["health"].removesuffix("/api/health")
    if product == "lawkey":
        _get_ok(f"{base}/api/document-presets", label="document_presets")
        print("[standalone] smoke passed: health, original landing, original app route, document presets")
        return
    query = urllib.parse.urlencode({"q": "test", "limit": "1"})
    _get_ok(f"{base}/api/{product}/search?{query}", label="search")
    print("[standalone] smoke passed: health, landing, chat, search")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fallback path: apply optional unified diff, configure DB/API/engine/frontend, and run one product server.",
    )
    parser.add_argument("--project-dir", type=Path, default=None, help="Platform root. Defaults to the repository root.")
    parser.add_argument("--product", default="islam", help="Product key. Default: islam because a small fixture DB is included.")
    parser.add_argument("--diff", type=Path, default=None, help="Unified diff/patch to apply before verification and server start.")
    parser.add_argument("--db", type=Path, default=None, help="Product corpus DB path override. Sets the correct RELIGION_*_DB_PATH variable.")
    parser.add_argument("--allow-missing-db", action="store_true", help="Start even when the selected product DB is missing. API search/answer will return 503.")
    parser.add_argument("--llm", choices=("auto", "disabled", "real"), default="auto", help="auto uses real keys when configured, otherwise deterministic writer-required mode.")
    parser.add_argument("--install-deps", action="store_true", help="Install requirements.txt if runtime dependencies are missing.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip repository contract/static parity checks.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip HTTP smoke after server start.")
    parser.add_argument("--exit-after-smoke", action="store_true", help="Start the server, run smoke checks, then stop it.")
    parser.add_argument("--no-open-browser", action="store_true", help="Do not open the landing page in the default browser.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Override server port. Default is the product port.")
    parser.add_argument("--reuse-port", action="store_true", help="Do not auto-select a new port if the requested one is already open.")
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        project_root = detect_project_root(args.project_dir)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        install_dependencies_if_requested(args.install_deps, project_root=project_root)
        checkpoint = apply_diff_if_requested(args.diff, project_root=project_root)
        db_path = resolve_product_db(args.product, args.db, env, project_root=project_root, allow_missing_db=args.allow_missing_db)
        llm_mode = configure_llm_mode(args.llm, env)
        print(f"[standalone] project={project_root}")
        print(f"[standalone] product={args.product} db={db_path} llm={llm_mode}")
        if checkpoint is not None:
            print(f"[standalone] rollback checkpoint={checkpoint}")
        run_verification(args.skip_verify, project_root=project_root)
        return run_server(args, env, project_root=project_root)
    except KeyboardInterrupt:
        print("\n[standalone] interrupted")
        return 130
    except StandaloneError as exc:
        print(f"[standalone] ERROR: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"[standalone] command failed with exit {exc.returncode}: {' '.join(exc.cmd)}", file=sys.stderr)
        return int(exc.returncode or 1)


def _load_metadata(project_root: Path | None = None) -> dict[str, Any]:
    root = detect_project_root(project_root).resolve()
    cached = _METADATA_CACHE.get(root)
    if cached is not None:
        return cached
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    product_app = importlib.import_module("apps.product_app")
    products = importlib.import_module("shared_platform.products")
    metadata = {
        "ports": dict(product_app.PRODUCT_PORTS),
        "landing_routes": dict(product_app.PRODUCT_LANDING_ROUTES),
        "chat_routes": dict(product_app.PRODUCT_CHAT_ROUTES),
        "get_product": products.get_product,
        "db_paths": {},
    }
    for key, item in EXTERNAL_PRODUCTS.items():
        metadata["ports"][key] = int(item["port"])
        metadata["landing_routes"][key] = str(item["landing"])
        metadata["chat_routes"][key] = str(item["chat"])
        metadata["db_paths"][key] = str(item["db"])
    _METADATA_CACHE[root] = metadata
    return metadata


def _normalize_product(product: str, *, project_root: Path | None = None) -> str:
    key = str(product or "").strip().lower()
    metadata = _load_metadata(project_root)
    if key not in metadata["ports"]:
        raise StandaloneError(f"unknown product: {product}")
    return key


def _choose_diff_apply_method(diff_path: Path, diff_paths: set[Path], *, project_root: Path) -> tuple[str, Path]:
    errors: list[str] = []
    for root in _candidate_apply_roots(diff_paths, project_root=project_root):
        git = shutil.which("git")
        if git:
            checked = subprocess.run([git, "apply", "--check", str(diff_path)], cwd=root, text=True, capture_output=True)
            if checked.returncode == 0:
                return "git", root
            errors.append(f"git apply --check from {root}: {checked.stderr.strip() or checked.stdout.strip()}")
        patch = shutil.which("patch")
        if patch:
            checked = subprocess.run([patch, "--dry-run", "-p1", "-i", str(diff_path)], cwd=root, text=True, capture_output=True)
            if checked.returncode == 0:
                return "patch", root
            errors.append(f"patch --dry-run from {root}: {checked.stderr.strip() or checked.stdout.strip()}")
    detail = "\n".join(error for error in errors if error)
    raise StandaloneError("diff did not apply cleanly. No files were changed.\n" + detail)


def _candidate_apply_roots(diff_paths: set[Path], *, project_root: Path) -> list[Path]:
    roots: list[Path] = []
    project_rel = _relative_to_repo(project_root)
    if project_rel and any(path.parts[: len(project_rel.parts)] == project_rel.parts for path in diff_paths):
        roots.append(REPO_ROOT)
    roots.append(project_root)
    if REPO_ROOT not in roots:
        roots.append(REPO_ROOT)
    return roots


def _relative_to_repo(path: Path) -> Path | None:
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return None


def _assert_safe_relative_path(path: Path) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise StandaloneError(f"unsafe relative path: {path}")


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"[standalone] run: {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def _git_executable() -> str:
    git = shutil.which("git")
    if not git:
        raise StandaloneError("git executable is not available")
    return git


def _patch_executable() -> str:
    patch = shutil.which("patch")
    if not patch:
        raise StandaloneError("patch executable is not available")
    return patch


def _get_ok(url: str, *, label: str) -> None:
    with urllib.request.urlopen(url, timeout=8) as response:
        if response.status < 200 or response.status >= 400:
            raise StandaloneError(f"{label} smoke returned HTTP {response.status}: {url}")


def _port_is_open(host: str, port: int) -> bool:
    target_host = host if host != "0.0.0.0" else "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((target_host, int(port))) == 0


def _find_free_port(start: int) -> int:
    for port in range(max(1, int(start)), max(1, int(start)) + 100):
        if not _port_is_open("127.0.0.1", port):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    raise SystemExit(main())
