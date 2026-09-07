"""Run declared ClassEval unittest classes in a fresh isolated process.

This child is never run on the unisolated host with benchmark code. It does
not invoke upstream AutoTest.tear_down, which deletes unrelated cwd files.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import resource
import signal
import sys
import time
import types
import unittest


def main() -> None:
    payload = json.load(sys.stdin)
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, 2 * 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 ** 2, 64 * 1024 ** 2))
    started = time.monotonic()
    cases, expected = {}, []
    namespace = {"__name__": "classeval_candidate", "__file__": "/tmp/work/candidate.py"}
    source_lines = len(payload["source"].splitlines())
    module_name = payload.get("module_name", "classeval_candidate")
    current_methods = set()

    def trace(frame, event, arg):
        if (event == "call" and frame.f_code.co_filename == "candidate.py"
                and (not payload.get("reload_each_class") or frame.f_lineno <= source_lines)):
            current_methods.add(frame.f_code.co_name)
        return trace

    class Result(unittest.TestResult):
        def startTest(self, test):
            super().startTest(test)
            current_methods.clear()
            sys.settrace(trace)

        def stopTest(self, test):
            sys.settrace(None)
            item = cases.setdefault(test.id(), {"status": "error"})
            item["methods"] = sorted(current_methods)
            super().stopTest(test)

        def addSuccess(self, test):
            super().addSuccess(test)
            cases[test.id()] = {"status": "passed"}

        def addFailure(self, test, err):
            super().addFailure(test, err)
            cases[test.id()] = {"status": "failed", "message": self._exc_info_to_string(err, test)[-2000:]}

        def addError(self, test, err):
            super().addError(test, err)
            cases[test.id()] = {"status": "error", "message": self._exc_info_to_string(err, test)[-2000:]}

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            cases[test.id()] = {"status": "skipped", "message": reason}

        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            if err is not None:
                cases[test.id()] = {"status": "failed", "message": str(err[1])[:2000]}

    def flatten(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from flatten(test)
            else:
                yield test

    def timeout(signum, frame):
        raise TimeoutError("official5-second test-class timeout")

    def load_module():
        module = types.ModuleType(module_name)
        module.__file__ = "/tmp/work/candidate.py"
        sys.modules[module_name] = module
        combined = payload["source"] + "\n" + payload["test"]
        with open(module.__file__, "w") as handle:
            handle.write(combined)
        exec(compile(combined, "candidate.py", "exec"), module.__dict__)
        return module.__dict__

    fatal = None
    signal.signal(signal.SIGALRM, timeout)
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            if not payload.get("reload_each_class"):
                signal.alarm(5)
                exec(compile(payload["source"], "candidate.py", "exec"), namespace)
                exec(compile(payload["test"], "official_tests.py", "exec"), namespace)
                signal.alarm(0)
            for name in payload["test_classes"]:
                signal.alarm(5)
                group_ids = []
                try:
                    if payload.get("reload_each_class"):
                        namespace = load_module()
                    suite = unittest.TestLoader().loadTestsFromTestCase(namespace[name])
                    group_ids = [test.id() for test in flatten(suite)]
                    if not group_ids or set(group_ids) & set(expected):
                        raise ValueError("empty or duplicate declared test-class inventory")
                    expected.extend(group_ids)
                    suite.run(Result())
                except BaseException as exc:
                    sys.settrace(None)
                    if not group_ids:
                        fatal = f"{name}: {type(exc).__name__}: {exc}"
                    for case_id in group_ids:
                        if case_id not in cases:
                            cases[case_id] = {"status": "error", "message": str(exc)[:2000], "methods": []}
                finally:
                    signal.alarm(0)
                    sys.settrace(None)
    except BaseException as exc:
        fatal = f"{type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        sys.settrace(None)
    passed = (fatal is None and bool(expected) and set(expected) == set(cases)
              and all(c["status"] == "passed" for c in cases.values()))
    print(json.dumps({"passed": passed, "cases": cases, "expectedCount": len(expected),
                      "fatal": fatal, "durationSeconds": time.monotonic() - started}))


if __name__ == "__main__":
    main()
