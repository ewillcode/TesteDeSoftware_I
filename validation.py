"""Sprint 4 requirement traceability and evidence-based validation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from mutation import CASES


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    criterion: str
    source: str
    known_gap: str = ""


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    requirement_ids: tuple[str, ...]
    kind: str
    test_id: str = ""
    required: bool = True


REQUIREMENTS = (
    Requirement("R01", "Leitura do CAD0001", "Ler e exibir o arquivo real do programa.", "Manual Sprint 1, pp. 1-2"),
    Requirement("R02", "Relatórios Gemini", "Gerar relatórios das três técnicas a partir do fonte e dos resultados calculados.", "Manual Sprint 1, p. 1; pedidos posteriores"),
    Requirement("R03", "PCE", "Exibir classes de equivalência dos três parâmetros sem inventar regras do fonte.", "Kickoff, p. 1; Manual Sprint 1, p. 2"),
    Requirement("R04", "AVL e épsilon", "Derivar ε da escala DECIMAL(12,2) e usar os quatro pontos de fronteira.", "Kickoff, pp. 1-2; Manual Sprint 1, p. 1", "O app usa ε = 0,01 fixo; não deriva a escala do tipo declarado no fonte."),
    Requirement("R05", "Gráfico de fronteira", "Mostrar tabela e gráfico dos pontos On, Off, Interior e Exterior.", "Manual Sprint 1, p. 2"),
    Requirement("R06", "GFC visual", "Mapear e exibir o fluxo de controle das funções do CAD0001.", "Kickoff, pp. 1 e 3"),
    Requirement("R07", "Complexidade ciclomática", "Calcular V(G) a partir das arestas e dos nós por função.", "Kickoff, pp. 1 e 3"),
    Requirement("R08", "Pares Def-Uso", "Identificar definições e usos alcançáveis nas funções do CAD0001.", "Kickoff, pp. 1 e 4"),
    Requirement("R09", "Mutação e MS", "Executar a suíte fixa na função de cálculo e calcular MS com contagens exatas.", "Kickoff, pp. 1 e 4; escopo acordado para o módulo 3"),
    Requirement("R10", "Fonte com rolagem", "Conter o código-fonte em caixa de altura fixa com barra de rolagem.", "Pedido posterior do projeto"),
    Requirement("R11", "PDF por aba", "Exportar resultados e relatório de cada módulo em PDF legível.", "Pedido posterior do projeto"),
    Requirement("R12", "RTM bidirecional", "Responder as duas perguntas com requisitos, testes e evidências vinculados.", "Sprint 4, p. 5"),
    Requirement("R13", "Pitch verificável", "Apresentar roteiro de 2 a 3 minutos e PDF coerentes com a RTM.", "Sprint 4, p. 5; decisão desta sprint"),
)

CHECKS = (
    Check("A01", "GFC e V(G) por função", ("R06", "R07"), "auto", "test_analysis.StructuralTests.test_graph_complexities_and_decision_branches"),
    Check("A02", "Definições que alcançam usos", ("R08",), "auto", "test_analysis.StructuralTests.test_reaching_definitions_across_null_branch_and_sql"),
    Check("A03", "Mutantes, score e guarda do fonte", ("R09",), "auto", "test_analysis.MutationTests.test_exact_score_and_source_guard"),
    Check("A04", "Conteúdo básico do PDF", ("R11",), "auto", "test_analysis.MutationTests.test_pdf_bytes_include_both_results_and_report"),
    Check("A05", "Duas direções da RTM", ("R12",), "auto", "test_validation.ValidationTests.test_bidirectional_answers"),
    Check("A06", "Pitch preserva pendências", ("R13",), "auto", "test_validation.ValidationTests.test_pitch_preserves_gaps"),
    Check("A07", "Evidência expira após mudança", ("R12",), "auto", "test_validation.ValidationTests.test_fingerprint_changes_with_source"),
    Check("M01", "Fonte visível e rolagem funcional", ("R01", "R10"), "manual"),
    Check("M02", "Relatórios Gemini nas três abas", ("R02",), "manual"),
    Check("M03", "PCE fiel ao fonte", ("R03",), "manual"),
    Check("M05", "Tabela e gráfico dos quatro limites", ("R05",), "manual"),
    Check("M06", "GFC legível na interface", ("R06",), "manual"),
    Check("M07", "PDF legível nas quatro abas", ("R11", "R13"), "manual"),
    *(Check(f"C{index:02}", f"Suíte de mutação: {case.label}", ("R09",), "case", required=False) for index, case in enumerate(CASES, 1)),
)


def project_fingerprint(base_dir: Path) -> str:
    """Identify the code and tests to which session evidence applies."""
    paths = [base_dir / name for name in (
        "app.py", "structural.py", "mutation.py", "pdf_export.py", "validation.py", "validation_runner.py", "validation_ui.py", "cad0001_item_calculo.txt"
    )]
    paths.extend(sorted((base_dir / "tests").glob("test_*.py")))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(base_dir)).encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"<missing>")
    return digest.hexdigest()


def run_local_checks(base_dir: Path, source: str) -> dict:
    """Run fixed checks in a fresh interpreter so imports match current files."""
    empty = {"tests_run": 0, "outcomes": {}, "test_log": "", "mutation": None, "mutation_error": ""}
    try:
        if (base_dir / "cad0001_item_calculo.txt").read_text(encoding="utf-8") != source:
            raise RuntimeError("O fonte mudou durante a validação. Atualize a página e execute novamente.")
        completed = subprocess.run(
            [sys.executable, str(base_dir / "validation_runner.py")],
            cwd=base_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"Processo encerrou com código {completed.returncode}.")
        payload = json.loads(completed.stdout)
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
        payload = {**empty, "runner_error": str(error)}
    return {**payload, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _case_rows(auto_run: dict | None, manual: dict[str, dict] | None) -> list[dict]:
    outcomes = auto_run.get("outcomes", {}) if auto_run else {}
    mutation_cases = (auto_run.get("mutation") or {}).get("cases", []) if auto_run else []
    manual = manual or {}
    rows = []
    for check in CHECKS:
        if check.kind == "auto":
            observation = outcomes.get(check.test_id, {"status": "pending", "evidence": "Teste ainda não executado ou não encontrado."})
        elif check.kind == "manual":
            observation = manual.get(check.id, {"status": "pending", "evidence": "Inspeção não registrada."})
        else:
            index = int(check.id[1:]) - 1
            if index < len(mutation_cases):
                case = mutation_cases[index]
                observation = {"status": "executed", "evidence": f"Entradas: {', '.join(case['inputs'])}; saída original: {case['expected']}"}
            else:
                observation = {"status": "pending", "evidence": "Suíte de mutação não executada."}
        rows.append({**asdict(check), **observation})
    for test_id, observation in outcomes.items():
        if not any(check.test_id == test_id for check in CHECKS if check.kind == "auto"):
            rows.append({"id": test_id, "title": "Teste sem vínculo", "requirement_ids": (), "kind": "auto", "test_id": test_id, "required": False, **observation})
    return rows


def evaluate_matrix(auto_run: dict | None, manual: dict[str, dict] | None = None) -> dict:
    cases = _case_rows(auto_run, manual)
    requirements = []
    for requirement in REQUIREMENTS:
        linked = [case for case in cases if requirement.id in case["requirement_ids"]]
        required = [case for case in linked if case["required"]]
        if requirement.known_gap:
            status = "Lacuna"
        elif not required:
            status = "Sem caso"
        elif any(case["status"] == "failed" for case in required):
            status = "Reprovado"
        elif all(case["status"] == "passed" for case in required):
            status = "Validado"
        else:
            status = "Pendente"
        requirements.append({**asdict(requirement), "check_ids": [case["id"] for case in linked], "status": status})
    statuses = {row["status"] for row in requirements}
    forward = "Não" if statuses & {"Lacuna", "Sem caso", "Reprovado"} else "Pendente" if "Pendente" in statuses else "Sim"
    executed = [case for case in cases if case["status"] in {"passed", "failed", "executed"}]
    extras = [case for case in executed if not case["requirement_ids"]]
    reverse = "Pendente" if not executed else "Não" if extras else "Sim"
    return {
        "requirements": requirements,
        "cases": cases,
        "forward": forward,
        "reverse": reverse,
        "validated": sum(row["status"] == "Validado" for row in requirements),
        "total_requirements": len(requirements),
        "executed_cases": len(executed),
        "extra_cases": len(extras),
        "gaps": [row for row in requirements if row["status"] != "Validado"],
        "mutation": (auto_run or {}).get("mutation"),
        "run_at": (auto_run or {}).get("run_at"),
    }


def snapshot_digest(matrix: dict) -> str:
    return hashlib.sha256(json.dumps(matrix, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def pitch_facts(matrix: dict) -> dict:
    mutation = matrix.get("mutation") or {}
    negative_case = next((case for case in mutation.get("cases", []) if case["case"] == "valor negativo"), None)
    return {
        "resposta_cobertura": matrix["forward"],
        "resposta_pertinencia": matrix["reverse"],
        "requisitos_validados": matrix["validated"],
        "total_requisitos": matrix["total_requirements"],
        "casos_executados": matrix["executed_cases"],
        "testes_extras": matrix["extra_cases"],
        "pendencias": [{"id": row["id"], "titulo": row["title"], "estado": row["status"], "motivo": row["known_gap"]} for row in matrix["gaps"]],
        "mutacao": {"mortos": mutation.get("killed"), "sobreviventes": mutation.get("survived"), "ms": str(mutation["score"]) if mutation else None},
        "resultado_negativo": negative_case["expected"] if negative_case else None,
    }


def build_pitch_template(facts: dict) -> str:
    """Give an honest, usable script when Gemini is unavailable."""
    pending = "; ".join(f"{item['id']} ({item['estado']}): {item['motivo'] or item['titulo']}" for item in facts["pendencias"])
    mutation = facts["mutacao"]
    mutation_text = (
        f"Na suíte fixa da função de cálculo, {mutation['mortos']} de "
        f"{mutation['mortos'] + mutation['sobreviventes']} mutantes foram mortos; "
        f"o MS desse catálogo foi {mutation['ms']}%."
        if mutation["mortos"] is not None else "O motor de mutação ainda aguarda execução nesta validação."
    )
    negative = (
        f"Um valor negativo produziu {facts['resultado_negativo']} no código entregue, "
        "enquanto o guia didático esperava o código de erro -1."
        if facts["resultado_negativo"] is not None else
        "A divergência entre o guia e o tratamento de valores negativos deve ser conferida na demonstração."
    )
    return (
        "# Pitch — TestingStudio Web\n\n"
        "Nosso projeto surgiu de uma pergunta simples: como verificar, de modo explicável, "
        "se uma aplicação atende ao que foi especificado? Usamos o programa CAD0001 como "
        "objeto de estudo e construímos o TestingStudio Web em Streamlit. Ele reúne uma auditoria "
        "de Caixa-Preta, análise estrutural, fluxo de dados e teste de mutação em um único lugar.\n\n"
        "Na primeira etapa, examinamos classes de equivalência e valores de fronteira. "
        f"{negative} Essa diferença mostra por que a expectativa do documento precisa ser comparada com o fonte real. "
        "Na segunda etapa, mapeamos o grafo de fluxo de controle das funções e calculamos "
        "a complexidade ciclomática. Na terceira, relacionamos definições e usos das variáveis "
        f"e executamos mutantes controlados. {mutation_text}\n\n"
        "Agora, na quarta sprint, usamos uma matriz de rastreabilidade nos dois sentidos. "
        f"A pergunta 'Tudo o que foi pedido foi coberto?' recebeu: {facts['resposta_cobertura']}. "
        f"A pergunta 'Tudo o que foi testado foi pedido?' recebeu: {facts['resposta_pertinencia']}. "
        f"Temos {facts['requisitos_validados']} de {facts['total_requisitos']} requisitos validados "
        f"e {facts['casos_executados']} casos executados nesta rodada. "
        f"As pendências registradas são: {pending or 'nenhuma'}.\n\n"
        "Nosso resultado é uma trilha verificável entre requisito, teste e evidência. "
        "O escore de mutação se refere apenas aos mutantes e à suíte apresentados; "
        "as rotinas transacionais do Informix não foram executadas. A matriz indica "
        "o que já foi demonstrado e o que ainda precisa ser concluído."
    )
