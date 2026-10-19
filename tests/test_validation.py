from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mutation import run_mutation
from validation import CHECKS, build_pitch_template, evaluate_matrix, pitch_facts, project_fingerprint


SOURCE = (ROOT / "cad0001_item_calculo.txt").read_text(encoding="utf-8")


class ValidationTests(unittest.TestCase):
    def _completed(self):
        auto = {
            "run_at": "2026-10-19T12:00:00+00:00",
            "outcomes": {check.test_id: {"status": "passed", "evidence": "Aprovado."} for check in CHECKS if check.kind == "auto"},
            "mutation": run_mutation(SOURCE),
        }
        manual = {check.id: {"status": "passed", "evidence": "Conferido na interface."} for check in CHECKS if check.kind == "manual"}
        return auto, manual

    def test_bidirectional_answers(self):
        initial = evaluate_matrix(None)
        self.assertEqual((initial["forward"], initial["reverse"]), ("Não", "Pendente"))
        auto, manual = self._completed()
        complete = evaluate_matrix(auto, manual)
        self.assertEqual((complete["forward"], complete["reverse"]), ("Não", "Sim"))
        self.assertEqual(next(row["status"] for row in complete["requirements"] if row["id"] == "R04"), "Lacuna")
        auto["outcomes"]["test_extra.Unspecified.test_unrequested"] = {"status": "passed", "evidence": "Sem requisito."}
        self.assertEqual(evaluate_matrix(auto, manual)["reverse"], "Não")
        auto["outcomes"][CHECKS[0].test_id] = {"status": "failed", "evidence": "Falhou."}
        failed = evaluate_matrix(auto, manual)
        self.assertEqual(next(row["status"] for row in failed["requirements"] if row["id"] == "R06"), "Reprovado")

    def test_pitch_preserves_gaps(self):
        auto, manual = self._completed()
        facts = pitch_facts(evaluate_matrix(auto, manual))
        script = build_pitch_template(facts)
        self.assertIn("R04 (Lacuna)", script)
        self.assertIn("Tudo o que foi pedido foi coberto?' recebeu: Não", script)
        self.assertIn("5 de 5 mutantes", script)
        self.assertIn("-0.02", script)

    def test_fingerprint_changes_with_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("primeira versão", encoding="utf-8")
            before = project_fingerprint(root)
            (root / "app.py").write_text("segunda versão", encoding="utf-8")
            self.assertNotEqual(before, project_fingerprint(root))


if __name__ == "__main__":
    unittest.main()
