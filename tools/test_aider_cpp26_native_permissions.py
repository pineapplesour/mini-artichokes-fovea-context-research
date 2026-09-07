"""No-model permission-profile smoke test for the Aider C++26 adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

from tools import run_aider_cpp26_image_representation as assay
from tools.run_plain_codex_file_agent import codex_installation


class AiderCpp26NativePermissionTests(unittest.TestCase):
    def test_native_command_uses_active_permission_config(self):
        with tempfile.TemporaryDirectory(prefix="aider-cpp26-command-") as temp:
            root = Path(temp)
            profile, _ = assay.write_permission_profile(root)
            image = root / "page.png"
            image.write_bytes(b"not-a-model-input")
            pair = root / "pair"
            pair.mkdir()
            fake = [
                "bwrap", "--dir", "/tmp/codex-home", "--ro-bind", "/host/auth",
                "/tmp/codex-home/auth.json", "--proc", "/proc", "node", "codex.js",
                "exec", "--ephemeral", "--ignore-user-config", "--sandbox",
                "danger-full-access", "--cd", "/tmp/work", "--model", assay.MODEL,
                "--config", "features.shell_tool=true", "--json", "-",
            ]
            transformed = assay._native_command(fake, profile, [image], pair)
            self.assertNotIn("--sandbox", transformed)
            self.assertNotIn("--profile", transformed)
            self.assertNotIn("-p", transformed)
            self.assertNotIn("--ignore-user-config", transformed)
            self.assertNotIn("sandbox_mode", " ".join(transformed))
            self.assertIn("--config", transformed)
            self.assertIn('approval_policy="never"', transformed)
            self.assertIn('default_permissions="paired"', transformed)
            self.assertIn("/tmp/codex-home/config.toml", transformed)
            self.assertIn("--image", transformed)
            self.assertIn("/tmp/pair-inputs", transformed)
            self.assertIn("features.shell_tool=true", transformed)

    def test_nested_outer_bwrap_codex_profile_is_no_model_and_isolated(self):
        bwrap = shutil.which("bwrap")
        if not bwrap:
            self.skipTest("bwrap unavailable")
        node_root, codex_js = codex_installation()
        node_root, codex_js = Path(node_root).resolve(), Path(codex_js).resolve()
        try:
            codex_rel = codex_js.relative_to(node_root)
        except ValueError as exc:
            self.fail(f"codex entrypoint is outside its node installation: {exc}")
        with tempfile.TemporaryDirectory(prefix="aider-cpp26-profile-runtime-") as temp:
            root = Path(temp)
            profile, profile_sha = assay.write_permission_profile(root)
            fake_auth_dir = root / "fake-codex-home"
            fake_auth_dir.mkdir()
            fake_auth = fake_auth_dir / "auth.json"
            fake_auth.write_text("DUMMY-AUTH-SENTINEL", encoding="utf-8")
            workspace = root / "workspace"
            workspace.mkdir()
            evidence = root / "pair-inputs"
            evidence.mkdir()
            (evidence / "context.json").write_text(
                json.dumps({"evidence": "read-only", "schemaVersion": 1}),
                encoding="utf-8",
            )
            image = root / "page.png"
            image.write_bytes(b"PNG-READONLY-EVIDENCE")

            # Keep a real listener in the host/outer network namespace.  The
            # outer adapter intentionally does not unshare networking; only
            # the named Codex permission profile should stop this connect.
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener_port = listener.getsockname()[1]
            script = (
                "import errno, json, socket\n"
                "from pathlib import Path\n"
                "auth_path = Path('/tmp/codex-home/auth.json')\n"
                "try:\n"
                "    auth_path.read_bytes()\n"
                "    auth_status = 'visible'\n"
                "except PermissionError:\n"
                "    auth_status = 'denied'\n"
                "except FileNotFoundError:\n"
                "    auth_status = 'hidden'\n"
                "work_path = Path('/tmp/work/runtime-write.txt')\n"
                "work_path.write_text('workspace-write-ok', encoding='utf-8')\n"
                "pair_text = Path('/tmp/pair-inputs/context.json').read_text(encoding='utf-8')\n"
                "image_bytes = Path('/tmp/representation-images/000-page.png').read_bytes()\n"
                "try:\n"
                "    sock = socket.socket()\n"
                "    sock.settimeout(0.25)\n"
                f"    sock.connect(('127.0.0.1', {listener_port}))\n"
                "    sock.close()\n"
                "    network_status = 'connected'\n"
                "except PermissionError:\n"
                "    network_status = 'denied'\n"
                "except TimeoutError:\n"
                "    network_status = 'timeout'\n"
                "except OSError as exc:\n"
                "    network_status = 'oserror:' + errno.errorcode.get(exc.errno, str(exc.errno))\n"
                "print(json.dumps({'auth': auth_status, 'network': network_status,\n"
                "    'workspaceWrite': work_path.read_text(encoding='utf-8'),\n"
                "    'evidenceRead': json.loads(pair_text)['evidence'],\n"
                "    'imageBytes': image_bytes.decode('ascii')}))\n"
            )
            command = [
                bwrap, "--die-with-parent", "--new-session", "--unshare-pid",
                "--unshare-ipc", "--unshare-uts",
                "--ro-bind", "/", "/", "--tmpfs", "/tmp", "--proc", "/proc",
                "--dev", "/dev", "--dir", "/tmp/codex-home", "--ro-bind",
                str(fake_auth), "/tmp/codex-home/auth.json", "--ro-bind", str(profile),
                "/tmp/codex-home/config.toml", "--dir", "/tmp/work", "--bind",
                str(workspace), "/tmp/work", "--dir", "/tmp/pair-inputs",
                "--ro-bind", str(evidence), "/tmp/pair-inputs", "--dir",
                "/tmp/representation-images", "--ro-bind", str(image),
                "/tmp/representation-images/000-page.png", "--dir", "/tmp/codex-node",
                "--ro-bind", str(node_root), "/tmp/codex-node", "--dir", "/tmp/home",
                "--clearenv", "--setenv", "HOME", "/tmp/home", "--setenv",
                "CODEX_HOME", "/tmp/codex-home", "--setenv", "PATH",
                "/tmp/codex-node/bin:/usr/local/bin:/usr/bin:/bin", "--setenv",
                "LANG", "C.UTF-8", "--chdir", "/tmp/work", "/tmp/codex-node/bin/node",
                f"/tmp/codex-node/{codex_rel.as_posix()}", "sandbox",
                "--permission-profile", assay.PROFILE_NAME, "--cd", "/tmp/work", "--",
                "/usr/bin/python3", "-c", script,
            ]
            try:
                done = subprocess.run(command, text=True, capture_output=True,
                                      timeout=30, check=False)
                self.assertEqual(done.returncode, 0, done.stderr or done.stdout)
                result = json.loads(done.stdout.strip())
                self.assertIn(result["auth"], {"denied", "hidden"})
                self.assertNotEqual(result["auth"], "visible")
                self.assertIn(result["network"], {"denied", "oserror:ENETUNREACH"})
                self.assertEqual(result["workspaceWrite"], "workspace-write-ok")
                self.assertEqual(result["evidenceRead"], "read-only")
                self.assertEqual(result["imageBytes"], "PNG-READONLY-EVIDENCE")
            finally:
                listener.close()

            redacted_argv = [
                "<dummy-auth-redacted>" if "auth.json" in value else value
                for value in command
            ]
            artifact = {
                "schemaVersion": 1,
                "modelCalls": 0,
                "profile": assay.PROFILE_NAME,
                "profileSha256": profile_sha,
                "argv": redacted_argv,
                "result": result,
            }
            artifact_path = root / "native-permission-smoke-result.json"
            artifact_path.write_text(json.dumps(artifact, indent=2) + "\n",
                                     encoding="utf-8")
            self.assertTrue(artifact_path.is_file())
            saved = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["modelCalls"], 0)
            self.assertIn("--permission-profile", saved["argv"])
            self.assertNotIn("--sandbox", saved["argv"])
            self.assertNotIn("DUMMY-AUTH-SENTINEL", artifact_path.read_text(encoding="utf-8"))
            durable_path = os.environ.get("AIDER_CPP26_PERMISSION_ARTIFACT")
            if durable_path:
                destination = Path(durable_path).resolve()
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(artifact, indent=2) + "\n",
                                       encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
