"""Source-checked Decimal execution and a finite mutation catalog for CAD0001."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from decimal import Decimal

from structural import _logical_lines, functions_from_source


@dataclass(frozen=True)
class Case:
    label: str
    values: tuple[Decimal | None, Decimal | None, Decimal | None]


CASES = [
    Case("p_val1 nulo", (None, Decimal("2.00"), Decimal("0.00"))),
    Case("p_val2 nulo", (Decimal("2.00"), None, Decimal("0.00"))),
    Case("p_val3 nulo", (Decimal("2.00"), Decimal("3.00"), None)),
    Case("cálculo comum", (Decimal("2.00"), Decimal("3.00"), Decimal("4.00"))),
    Case("valor negativo", (Decimal("-0.01"), Decimal("2.00"), Decimal("0.00"))),
]


@dataclass(frozen=True)
class Mutant:
    id: str
    description: str
    fallback_variable: str | None = None
    operator: str | None = None


MUTANTS = [
    Mutant("M1", "p_val1: NULL → 1", "p_val1"),
    Mutant("M2", "p_val2: NULL → 1", "p_val2"),
    Mutant("M3", "p_val3: NULL → 1", "p_val3"),
    Mutant("M4", "multiplicação: * → +", operator="multiply"),
    Mutant("M5", "soma final: + → −", operator="addition"),
]


def _expression(source: str) -> ast.Expression:
    functions = {name: (parameters, body) for name, parameters, body in functions_from_source(source)}
    if "cad0001_calcula_valor" not in functions:
        raise ValueError("A função cad0001_calcula_valor não foi encontrada.")
    parameters, body = functions["cad0001_calcula_valor"]
    if parameters != ["p_val1", "p_val2", "p_val3"]:
        raise ValueError("Os parâmetros da função de cálculo mudaram.")
    lines = [text for _, text in _logical_lines(body)]
    for variable in parameters:
        expected = rf"IF\s+{variable}\s+IS\s+NULL\s+THEN\s+LET\s+{variable}\s*=\s*0\s+END\s+IF"
        if sum(bool(re.fullmatch(expected, line, re.I)) for line in lines) != 1:
            raise ValueError(f"O tratamento de NULL de {variable} não corresponde ao motor de mutação.")
    assignments = [line for line in lines if line.upper().startswith("LET L_VAL_CALCULADO")]
    if len(assignments) != 1 or sum(line.upper() == "RETURN L_VAL_CALCULADO" for line in lines) != 1:
        raise ValueError("A atribuição ou o retorno do cálculo mudou.")
    expression = re.fullmatch(r"LET\s+l_val_calculado\s*=\s*(.+)", assignments[0], re.I)
    if not expression:
        raise ValueError("Expressão de cálculo não reconhecida.")
    allowed = [line for line in lines if not line.upper().startswith("DEFINE ")]
    if len(allowed) != 5:
        raise ValueError("A função de cálculo contém instruções adicionais não interpretadas.")
    tree = ast.parse(expression.group(1), mode="eval")
    root = tree.body
    if not (
        isinstance(root, ast.BinOp) and isinstance(root.op, ast.Add)
        and isinstance(root.left, ast.BinOp) and isinstance(root.left.op, ast.Mult)
        and isinstance(root.left.left, ast.Name) and root.left.left.id == "p_val1"
        and isinstance(root.left.right, ast.Name) and root.left.right.id == "p_val2"
        and isinstance(root.right, ast.Name) and root.right.id == "p_val3"
    ):
        raise ValueError("A fórmula não corresponde ao catálogo de mutantes disponível.")
    return tree


def _evaluate(tree: ast.Expression, values: dict[str, Decimal], mutant: Mutant | None) -> Decimal:
    def visit(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Mult):
                return left + right if mutant and mutant.operator == "multiply" else left * right
            if isinstance(node.op, ast.Add):
                return left - right if mutant and mutant.operator == "addition" else left + right
        raise ValueError("Operador não suportado no cálculo.")

    return visit(tree.body).quantize(Decimal("0.01"))


def run_mutation(source: str) -> dict:
    tree = _expression(source)

    def execute(case: Case, mutant: Mutant | None) -> Decimal:
        values = {}
        for name, value in zip(("p_val1", "p_val2", "p_val3"), case.values):
            values[name] = value if value is not None else Decimal(
                "1" if mutant and mutant.fallback_variable == name else "0"
            )
        return _evaluate(tree, values, mutant)

    baseline = {case.label: execute(case, None) for case in CASES}
    rows = []
    for mutant in MUTANTS:
        differences = [
            (case.label, baseline[case.label], execute(case, mutant))
            for case in CASES if baseline[case.label] != execute(case, mutant)
        ]
        witness = differences[0] if differences else None
        rows.append({
            "id": mutant.id,
            "alteration": mutant.description,
            "status": "Morto" if witness else "Sobrevivente",
            "killing_case": witness[0] if witness else "—",
            "original": str(witness[1]) if witness else "—",
            "mutant": str(witness[2]) if witness else "—",
        })
    killed = sum(row["status"] == "Morto" for row in rows)
    survived = len(rows) - killed
    return {
        "cases": [{"case": case.label, "inputs": [str(value) if value is not None else "NULL" for value in case.values], "expected": str(baseline[case.label])} for case in CASES],
        "mutants": rows,
        "killed": killed,
        "survived": survived,
        "score": Decimal(killed * 100) / Decimal(killed + survived),
    }
