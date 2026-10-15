from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mutation import run_mutation
from pdf_export import create_pdf
from structural import build_all_graphs, def_use_pairs


SOURCE = (ROOT / "cad0001_item_calculo.txt").read_text(encoding="utf-8")


class StructuralTests(unittest.TestCase):
    def test_graph_complexities_and_decision_branches(self):
        graphs = build_all_graphs(SOURCE)
        self.assertEqual(
            {graph.name: graph.complexity for graph in graphs},
            {"cad0001_main": 1, "cad0001_calcula_valor": 4, "cad0001_incluir": 3, "cad0001_alterar": 3, "cad0001_excluir": 3},
        )
        for graph in graphs:
            self.assertEqual(graph.complexity, graph.decisions + 1)
            for node in graph.nodes.values():
                if node.kind == "if":
                    self.assertEqual({branch for origin, _, branch in graph.edges if origin == node.id}, {"Sim", "Não"})

    def test_reaching_definitions_across_null_branch_and_sql(self):
        graphs = {graph.name: graph for graph in build_all_graphs(SOURCE)}
        calculation = def_use_pairs(graphs["cad0001_calcula_valor"])
        p1_formula = [pair for pair in calculation if pair["variable"] == "p_val1" and pair["use_line"] == 49]
        self.assertEqual({pair["definition_line"] for pair in p1_formula}, {None, 44})
        self.assertTrue(any(pair["variable"] == "p_val1" and pair["kind"] == "p-uso" and pair["use_line"] == 44 for pair in calculation))
        self.assertTrue(any(pair["variable"] == "l_val_calculado" and pair["definition_line"] == 49 and pair["use_line"] == 51 for pair in calculation))
        insertion = def_use_pairs(graphs["cad0001_incluir"])
        self.assertTrue(any(pair["variable"] == "sqlca.sqlcode" and pair["use_line"] == 86 and pair["origin"] == "fonte" for pair in insertion))


class MutationTests(unittest.TestCase):
    def test_exact_score_and_source_guard(self):
        result = run_mutation(SOURCE)
        self.assertEqual((result["killed"], result["survived"], result["score"]), (5, 0, 100))
        self.assertEqual([row["id"] for row in result["mutants"]], ["M1", "M2", "M3", "M4", "M5"])
        self.assertEqual(result["cases"][-1]["expected"], "-0.02")
        changed = SOURCE.replace("(p_val1 * p_val2) + p_val3", "(p_val1 * p_val2) - p_val3")
        with self.assertRaises(ValueError):
            run_mutation(changed)

    def test_pdf_bytes_include_both_results_and_report(self):
        pdf = create_pdf("Módulo de teste", [("Dados", [{"Escore": "100%", "Nota": "cálculo"}])], "# Relatório\nResultado do Gemini.")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"100%", pdf)
        self.assertIn(b"Resultado do Gemini", pdf)
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))


if __name__ == "__main__":
    unittest.main()
