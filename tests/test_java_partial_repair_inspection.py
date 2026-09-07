import tempfile
import unittest
from pathlib import Path

from tools.inspect_aider_java_partial_repairs import parse_cases, summarize


class PartialRepairInspectionTest(unittest.TestCase):
    def test_junit_statuses_are_not_all_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "TEST-example.xml").write_text('<testsuite><testcase classname="C" name="ok"/>'
                '<testcase classname="C" name="bad"><failure message="wrong"/></testcase>'
                '<testcase classname="C" name="skip"><skipped/></testcase></testsuite>')
            cases = parse_cases(root)
            self.assertEqual([c["status"] for c in cases.values()], ["passed", "failed", "skipped"])

    def test_complementarity_is_not_a_solution(self):
        captures = {}
        for label, statuses in [("plain", ["passed", "failed"]), ("graph", ["failed", "passed"])]:
            captures[label] = {"tasks": {"task": {"passed": False,
                "cases": {str(i): {"status": status} for i, status in enumerate(statuses)}}}}
        result = summarize(captures)
        self.assertEqual(result["unresolvedWithFullObservedCoverage"], ["task"])
        self.assertFalse(result["tasks"]["task"]["alreadySolved"])
        self.assertEqual(result["tasks"]["task"]["unionBeyondBest"], 1)

    def test_missing_and_misaligned_reports_are_not_imputed(self):
        captures = {"plain": {"tasks": {"task": {"passed": False, "cases": {}}}},
                    "graph": {"tasks": {"task": {"passed": False, "cases": {"x": {"status": "failed"}}}}}}
        result = summarize(captures)
        self.assertEqual(result["tasks"]["task"]["noCaseReport"], ["plain"])
        self.assertEqual(result["unresolvedWithFullObservedCoverage"], [])
        captures["plain"]["tasks"]["task"]["cases"] = {"y": {"status": "passed"}}
        self.assertFalse(summarize(captures)["tasks"]["task"]["caseInventoryAligned"])
