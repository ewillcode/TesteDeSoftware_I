"""Isolated CLI runner used by the Sprint 4 validation button."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from mutation import run_mutation


class TrackingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def addSuccess(self, test):
        self.outcomes[test.id()] = {"status": "passed", "evidence": "Asserções aprovadas."}
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.outcomes[test.id()] = {"status": "failed", "evidence": self._exc_info_to_string(err, test)[-1000:]}
        super().addFailure(test, err)

    def addError(self, test, err):
        self.outcomes[test.id()] = {"status": "failed", "evidence": self._exc_info_to_string(err, test)[-1000:]}
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.outcomes[test.id()] = {"status": "pending", "evidence": f"Ignorado: {reason}"}
        super().addSkip(test, reason)


def main() -> None:
    root = Path(__file__).resolve().parent
    log = io.StringIO()
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        suite = unittest.TestLoader().discover(str(root / "tests"), pattern="test_*.py", top_level_dir=str(root / "tests"))
        result = unittest.TextTestRunner(stream=log, verbosity=1, resultclass=TrackingResult).run(suite)
        mutation = None
        mutation_error = ""
        try:
            mutation = run_mutation((root / "cad0001_item_calculo.txt").read_text(encoding="utf-8"))
            mutation["score"] = str(mutation["score"])
        except (OSError, UnicodeDecodeError, ValueError, ArithmeticError) as error:
            mutation_error = str(error)
    # Escape Unicode so Windows consoles using cp1252 can emit this JSON safely.
    print(json.dumps({
        "tests_run": result.testsRun,
        "outcomes": result.outcomes,
        "test_log": log.getvalue() + captured.getvalue(),
        "mutation": mutation,
        "mutation_error": mutation_error,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
