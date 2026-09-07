import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import run_aider_cpp26_image_representation as assay


class AiderImageRepresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.task, cls.manifest = assay._load_freeze(assay.DEFAULT_FREEZE)

    def test_fixed_twelve_session_schedule_and_full_track(self):
        self.assertEqual(len(self.manifest["tasks"]), 26)
        self.assertEqual(assay.BASELINE_PLAN,
                         (("T1", "text"), ("T2", "text"), ("I1", "image"), ("I2", "image")))
        self.assertEqual(assay.PAIR_PLAN,
                         (("TT", ("T1", "T2")), ("II", ("I1", "I2")),
                          ("TIa", ("T1", "I1")), ("TIb", ("I2", "T2"))))

    def test_image_prompt_has_no_full_instruction_duplicate(self):
        prompt = assay.build_image_prompt(self.task, self.manifest)
        self.assertIn("Allowed paths:", prompt)
        self.assertIn("Task index", prompt)
        for item in self.manifest["tasks"]:
            self.assertNotIn(item["instruction"], prompt)

    def test_profile_transform_keeps_shell_and_attaches_readonly_inputs(self):
        with tempfile.TemporaryDirectory(prefix="aider-image-command-") as temp:
            root = Path(temp)
            profile = root / "paired.config.toml"
            profile.write_text(assay.PROFILE_TEXT, encoding="utf-8")
            image = root / "page.png"
            image.write_bytes(b"not-a-model-input-in-this-no-call-test")
            fake = ["bwrap", "--dir", "/tmp/codex-home", "--ro-bind", "/host/auth",
                    "/tmp/codex-home/auth.json", "--proc", "/proc", "node",
                    "codex.js", "exec", "--sandbox", "danger-full-access",
                    "--model", assay.MODEL, "--config", "features.shell_tool=true", "-"]
            transformed = assay._native_command(fake, profile, [image], root)
            self.assertNotIn("--sandbox", transformed)
            self.assertIn('approval_policy="never"', transformed)
            self.assertIn('default_permissions="paired"', transformed)
            self.assertIn("--ro-bind", transformed)
            self.assertIn("--image", transformed)
            self.assertIn("/tmp/pair-inputs", transformed)
            self.assertIn("features.shell_tool=true", transformed)
            self.assertNotIn("--approve-for-me", transformed)

    def test_dry_run_reports_rendered_pages_without_execution(self):
        result = assay.dry_run(assay.DEFAULT_FREEZE)
        self.assertEqual(result["tasks"], 26)
        self.assertEqual(result["sessions"], 12)
        self.assertEqual(result["imageTextChars"], 51417)
        self.assertGreater(result["imagePageCount"], 0)
        self.assertEqual(result["agentTimeoutSeconds"], 900)

    @staticmethod
    def _attempt(task_ids, passed=()):
        rows = [json.dumps({"taskId": task_id, "passed": task_id in set(passed)})
                for task_id in task_ids]
        return SimpleNamespace(
            public_test=SimpleNamespace(stdout="\n".join(rows), exit_code=0,
                                        timed_out=False, duration_seconds=1.0),
            agent=SimpleNamespace(exit_code=0, timed_out=False, duration_seconds=1.0),
            patch_text="", patch_sha256="patch-sha", forbidden_files=(),
            workspace="/tmp/fake-workspace",
        )

    def test_inventory_requires_unique_manifest_order(self):
        expected = ("a", "b", "c")
        ordered = self._attempt(expected, ("a",))
        self.assertTrue(assay._evaluator_inventory(ordered, expected)["complete"])
        duplicate = SimpleNamespace(public_test=SimpleNamespace(
            stdout="\n".join(json.dumps({"taskId": task_id, "passed": False})
                                  for task_id in ("a", "b", "b"))))
        inventory = assay._evaluator_inventory(duplicate, expected)
        self.assertFalse(inventory["unique"])
        self.assertFalse(inventory["complete"])

    def test_gate_reports_scores_and_increments_without_iid_statistics(self):
        ids = tuple(f"task-{index:02d}" for index in range(26))
        attempts = {}
        for label in ("TT_G", "TT_O", "II_G", "II_O", "TIa_G", "TIa_O", "TIb_G", "TIb_O"):
            count = {"TT_O": 1, "II_O": 1, "TIa_O": 2, "TIb_O": 2}.get(label, 0)
            attempts[label] = self._attempt(ids, ids[:count])
        gate = assay._gate(attempts, ids)
        self.assertEqual(gate["scores"]["TT_O"], 1 / 26)
        self.assertEqual(gate["increments"]["TT"], 1 / 26)
        self.assertEqual(gate["integerGateCounts"]["mixedInteractionNumerator"], 2)
        self.assertTrue(all(gate["criteria"].values()))
        self.assertTrue(gate["eligible"])
        self.assertIn("interaction", gate)
        self.assertNotIn("pValue", gate)

    def test_stage_pair_inputs_records_first_passing_anchor(self):
        task_ids = tuple(item["taskId"] for item in self.manifest["tasks"])
        with tempfile.TemporaryDirectory(prefix="aider-pair-stage-test-") as temp:
            root = Path(temp)
            workspaces = {}
            for label in ("A", "B"):
                workspace = root / f"workspace-{label}"
                assay.prepare_workspace(self.source, self.task.base_ref, workspace)
                workspaces[label] = workspace
            attempts = {
                "A": self._attempt(task_ids, (task_ids[0],)),
                "B": self._attempt(task_ids, ()),
            }
            attempts["A"].workspace = str(workspaces["A"])
            attempts["B"].workspace = str(workspaces["B"])
            pair_root, _, context, anchors = assay.stage_pair_inputs(
                self.source, self.task, self.manifest, root / "pairs", "TEST", ("A", "B"), attempts
            )
            self.assertEqual(context["decisions"][0]["selected"], "A")
            self.assertTrue(anchors)
            self.assertEqual(context["anchorSha256"],
                             {path: assay._sha(payload) for path, payload in sorted(anchors.items())})
            self.assertTrue((pair_root / "context.json").is_file())

    def test_stage_pair_inputs_rejects_failed_parent_before_staging(self):
        task_ids = tuple(item["taskId"] for item in self.manifest["tasks"])
        with tempfile.TemporaryDirectory(prefix="aider-pair-invalid-parent-") as temp:
            root = Path(temp)
            workspaces = {}
            for label in ("A", "B"):
                workspace = root / f"workspace-{label}"
                assay.prepare_workspace(self.source, self.task.base_ref, workspace)
                workspaces[label] = workspace
            attempts = {
                "A": self._attempt(task_ids, (task_ids[0],)),
                "B": self._attempt(task_ids, ()),
            }
            attempts["A"].workspace = str(workspaces["A"])
            attempts["B"].workspace = str(workspaces["B"])
            attempts["A"].agent.exit_code = 2
            with self.assertRaisesRegex(ValueError, "invalid baseline parent"):
                assay.stage_pair_inputs(
                    self.source, self.task, self.manifest, root / "pairs", "TEST", ("A", "B"), attempts
                )
            self.assertFalse((root / "pairs" / "TEST").exists())

    def test_load_freeze_rejects_manifest_hash_mismatch(self):
        with tempfile.TemporaryDirectory(prefix="aider-freeze-hash-") as temp:
            freeze = Path(temp) / "freeze"
            shutil.copytree(assay.DEFAULT_FREEZE, freeze)
            metadata_path = freeze / "freeze.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["manifestSha256"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest hash mismatch"):
                assay._load_freeze(freeze)

    def test_main_preserves_preexisting_run_root_on_file_exists(self):
        with tempfile.TemporaryDirectory(prefix="aider-existing-run-") as temp:
            run_root = Path(temp) / "run"
            run_root.mkdir()
            marker = run_root / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            with patch.object(assay, "run_experiment", side_effect=FileExistsError("already exists")):
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(
                        assay.main(["--execute", "--run-root", str(run_root)]), 1
                    )
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            self.assertFalse((run_root / "error.json").exists())

    def test_main_marks_new_partial_run_incomplete_after_exception(self):
        with tempfile.TemporaryDirectory(prefix="aider-partial-run-") as temp:
            run_root = Path(temp) / "run"

            def fail(_freeze_root, requested_root):
                requested_root = Path(requested_root)
                requested_root.mkdir(parents=True)
                (requested_root / "result.json").write_text(
                    json.dumps({"schemaVersion": 1, "status": "running", "keep": True}),
                    encoding="utf-8",
                )
                raise RuntimeError("synthetic setup failure")

            with patch.object(assay, "run_experiment", side_effect=fail):
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(
                        assay.main(["--execute", "--run-root", str(run_root)]), 1
                    )
            result = json.loads((run_root / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "incomplete")
            self.assertTrue(result["keep"])
            self.assertEqual(result["error"]["type"], "RuntimeError")
            self.assertTrue((run_root / "error.json").is_file())


if __name__ == "__main__":
    unittest.main()
