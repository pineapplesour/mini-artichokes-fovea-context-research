"""No-model tests for the immutable paired probe helper."""
from __future__ import annotations

import hashlib
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from tools import classeval_native_pair_probe as helper


class NativePairProbeTests(unittest.TestCase):
    def test_nested_pair_smoke_masks_network_and_auth(self):
        if not shutil.which("bwrap"):
            self.skipTest("bwrap unavailable")
        with tempfile.TemporaryDirectory(prefix="paired-helper-test-") as temp:
            root = Path(temp)
            candidate = (
                "import socket\n"
                "from pathlib import Path\n"
                "class Demo:\n"
                "    def __init__(self):\n"
                "        self.value = 3\n"
                "    def update(self):\n"
                "        self.value += 2\n"
                "        return self.value\n"
            )
            (root / "a.py").write_text(candidate, encoding="utf-8")
            (root / "b.py").write_text(candidate + "\n# byte-distinct\n", encoding="utf-8")
            probe = root / "probe.py"
            probe.write_text(
                "from pathlib import Path\n"
                "import socket\n"
                "def probe(candidate):\n"
                "    d = candidate.Demo()\n"
                "    value = d.update()\n"
                "    try:\n"
                "        s = socket.socket()\n"
                "        s.settimeout(0.25)\n"
                "        s.connect(('203.0.113.1', 80))\n"
                "        s.close()\n"
                "        network_denied = False\n"
                "    except PermissionError:\n"
                "        network_status = 'denied'\n"
                "    except TimeoutError:\n"
                "        network_status = 'timeout'\n"
                "    except OSError as exc:\n"
                "        network_status = 'unreachable:' + type(exc).__name__\n"
                "    return {'value': value, 'networkStatus': network_status,\n"
                "            'authVisible': Path('/tmp/codex-home/auth.json').exists(),\n"
                "            'cwd': str(Path.cwd())}\n",
                encoding="utf-8",
            )
            context = root / "context.json"
            context.write_text(json.dumps({
                "sourceA": str(root / "a.py"), "sourceB": str(root / "b.py"),
                "sourceSha256A": hashlib.sha256((root / "a.py").read_bytes()).hexdigest(),
                "sourceSha256B": hashlib.sha256((root / "b.py").read_bytes()).hexdigest(),
                "python": "/home/pineapple/miniconda3/bin/python3",
                "pythonBase": "/home/pineapple/miniconda3",
                "venv": str(Path(__file__).resolve().parents[1] / ".runtime/classeval-v1-env"),
                "nltkData": str(Path(__file__).resolve().parents[1] / ".runtime/classeval-nltk-data"),
                "timeoutSeconds": 5,
            }), encoding="utf-8")
            done = subprocess.run(
                [sys.executable, str(Path(helper.__file__)), "--context", str(context),
                 "--probe", str(probe)], text=True, capture_output=True,
                timeout=20, check=False)
            self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads(done.stdout)
            self.assertEqual(result["probeSHA256"], helper._sha(probe.read_bytes()))
            self.assertEqual(set(result["candidates"]), {"A", "B"})
            self.assertTrue(result["separateProcesses"])
            for label, item in result["candidates"].items():
                self.assertIsNone(item["exception"], (label, item))
                self.assertEqual(item["output"]["value"], 5)
                status = item["output"]["networkStatus"]
                self.assertTrue(status == "denied" or status.startswith("unreachable:"), status)
                self.assertNotEqual(status, "timeout")
                self.assertFalse(item["output"]["authVisible"])
                self.assertIn("__init__", item["visitedMethods"])
                self.assertIn("update", item["visitedMethods"])
            self.assertIsInstance(result["candidates"]["A"]["pid"], int)
            self.assertIsInstance(result["candidates"]["B"]["pid"], int)

    def test_context_rejects_mutated_candidate_hash(self):
        with tempfile.TemporaryDirectory(prefix="paired-helper-hash-") as temp:
            root = Path(temp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "b.py").write_text("x = 2\n", encoding="utf-8")
            context = root / "context.json"
            context.write_text(json.dumps({
                "sourceA": str(root / "a.py"), "sourceB": str(root / "b.py"),
                "sourceSha256A": "0" * 64, "sourceSha256B": "0" * 64,
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                helper._context(context)

    def test_probe_is_hashed_without_following_symlink(self):
        with tempfile.TemporaryDirectory(prefix="paired-helper-probe-") as temp:
            path = Path(temp) / "probe.py"
            path.write_text("def probe(candidate):\n    return 1\n", encoding="utf-8")
            self.assertEqual(helper._sha(path.read_bytes()), hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertFalse(path.is_symlink())

    def test_symlink_probe_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="paired-helper-link-") as temp:
            root = Path(temp)
            target, link = root / "real.py", root / "link.py"
            target.write_text("def probe(candidate):\n    return 1\n", encoding="utf-8")
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                helper._file(link, "probe")

    def test_pair_uses_one_probe_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="paired-helper-snapshot-") as temp:
            root = Path(temp)
            a, b = root / "a.py", root / "b.py"
            a.write_text("x = 1\n", encoding="utf-8")
            b.write_text("x = 2\n", encoding="utf-8")
            original_probe = root / "probe.py"
            original_probe.write_text("def probe(candidate):\n    return 1\n", encoding="utf-8")
            context = root / "context.json"
            context.write_text(json.dumps({
                "sourceA": str(a), "sourceB": str(b),
                "sourceSha256A": helper._sha(a.read_bytes()),
                "sourceSha256B": helper._sha(b.read_bytes()),
            }), encoding="utf-8")
            seen = []

            def fake_run(ctx, source, label, probe, probe_sha):
                seen.append(probe.read_bytes())
                if label == "A":
                    original_probe.write_text("def probe(candidate):\n    return 999\n", encoding="utf-8")
                return {"schemaVersion": 1, "candidate": label}

            args = SimpleNamespace(context=context, probe=original_probe)
            with mock.patch.object(helper, "_run_one", side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()):
                helper._pair(args)
            self.assertEqual(seen[0], seen[1])
            self.assertNotEqual(seen[0], original_probe.read_bytes())

    def test_run_one_rejects_mismatched_child_metadata(self):
        with tempfile.TemporaryDirectory(prefix="paired-helper-meta-") as temp:
            root = Path(temp)
            source, probe = root / "a.py", root / "probe.py"
            source.write_text("x = 1\n", encoding="utf-8")
            probe.write_text("def probe(candidate):\n    return 1\n", encoding="utf-8")
            source_sha, probe_sha = helper._sha(source.read_bytes()), helper._sha(probe.read_bytes())
            child = {"schemaVersion": 1, "candidate": "B", "sourceSha256": source_sha,
                     "probeSHA256": probe_sha, "output": {}, "exception": None,
                     "visitedMethods": [], "stdout": "", "stderr": "", "durationSeconds": 0.1}
            done = SimpleNamespace(returncode=0, stdout=json.dumps(child), stderr="")
            ctx = {"python": sys.executable, "timeout": 1}
            with mock.patch.object(helper, "_command", return_value=["unused"]), \
                 mock.patch.object(helper.subprocess, "run", return_value=done):
                item = helper._run_one(ctx, source, "A", probe, probe_sha)
            self.assertEqual(item["exception"]["type"], "ValueError")
            self.assertIn("metadata", item["exception"]["message"])

    def test_run_one_rejects_nonzero_child(self):
        with tempfile.TemporaryDirectory(prefix="paired-helper-exit-") as temp:
            root = Path(temp)
            source, probe = root / "a.py", root / "probe.py"
            source.write_text("x = 1\n", encoding="utf-8")
            probe.write_text("def probe(candidate):\n    return 1\n", encoding="utf-8")
            done = SimpleNamespace(returncode=7, stdout="{}\n", stderr="child error")
            ctx = {"python": sys.executable, "timeout": 1}
            with mock.patch.object(helper, "_command", return_value=["unused"]), \
                 mock.patch.object(helper.subprocess, "run", return_value=done):
                item = helper._run_one(ctx, source, "A", probe, helper._sha(probe.read_bytes()))
            self.assertIn("exited", item["exception"]["message"])
            self.assertEqual(item["exitCode"], 7)

    def test_outer_bwrap_codex_profile_denies_fake_credential(self):
        bwrap, codex = shutil.which("bwrap"), shutil.which("codex")
        if not bwrap or not codex:
            self.skipTest("bwrap/codex unavailable")
        with tempfile.TemporaryDirectory(prefix="paired-profile-") as temp:
            root = Path(temp)
            fake_dir, fake = root / "fake-codex-home", root / "fake-codex-home" / "auth.json"
            fake_dir.mkdir()
            fake.write_text("SENTINEL", encoding="utf-8")
            self.assertTrue(fake.exists())
            sandbox_fake_dir = Path("/tmp/paired-fake-codex-home")
            sandbox_fake = sandbox_fake_dir / "auth.json"
            profile = f'permissions.paired.filesystem={{"{sandbox_fake_dir}"="deny"}}'
            script = (
                "from pathlib import Path\nimport socket\n"
                f"p=Path({str(sandbox_fake)!r})\n"
                "try:\n auth='visible' if p.exists() else 'hidden'\n"
                "except PermissionError:\n auth='denied'\n"
                "assert auth in ('denied', 'hidden'), auth\n"
                "status='connected'\n"
                "try:\n"
                " s=socket.socket(); s.settimeout(.25); s.connect(('203.0.113.1',80)); s.close()\n"
                "except PermissionError:\n status='denied'\n"
                "except TimeoutError:\n status='timeout'\n"
                "except OSError as e:\n status='unreachable:'+type(e).__name__\n"
                "assert status == 'denied' or status.startswith('unreachable:'), status\n"
                "assert status != 'timeout'\n"
                "print('PROFILE-SMOKE', auth, status)"
            )
            command = [bwrap, "--die-with-parent", "--new-session", "--unshare-all",
                       "--ro-bind", "/", "/", "--tmpfs", "/tmp",
                       "--ro-bind", str(fake_dir), str(sandbox_fake_dir),
                       "--proc", "/proc", "--dev", "/dev",
                       "--chdir", "/home/pineapple", codex, "sandbox", "-P", "paired",
                       "-c", 'permissions.paired.extends=":workspace"', "-c", profile,
                       "-c", 'permissions.paired.network={enabled=false}',
                       "--", sys.executable, "-c", script]
            done = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
            self.assertEqual(done.returncode, 0, done.stderr or done.stdout)
            self.assertIn("PROFILE-SMOKE", done.stdout)
            self.assertTrue(fake.exists())


if __name__ == "__main__":
    unittest.main()
