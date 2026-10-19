"""Streamlit interface for the Sprint 4 traceability matrix and pitch."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from pdf_export import create_pdf
from validation import (
    CHECKS, build_pitch_template, evaluate_matrix, pitch_facts,
    project_fingerprint, run_local_checks, snapshot_digest,
)


STATUS_LABELS = {"pending": "Pendente", "passed": "Aprovado", "failed": "Reprovado"}
STATUS_VALUES = {value: key for key, value in STATUS_LABELS.items()}


def _manual_editor(saved: dict[str, dict], fingerprint: str) -> None:
    manual_checks = [check for check in CHECKS if check.kind == "manual"]
    rows = [{
        "ID": check.id,
        "Verificação": check.title,
        "Resultado": STATUS_LABELS.get(saved.get(check.id, {}).get("status", "pending"), "Pendente"),
        "Observação": saved.get(check.id, {}).get("evidence", "") if saved.get(check.id, {}).get("status") != "pending" else "",
    } for check in manual_checks]
    with st.form("manual_validation_form"):
        edited = st.data_editor(
            pd.DataFrame(rows), hide_index=True, width="stretch", num_rows="fixed",
            disabled=["ID", "Verificação"], key=f"manual_editor_{fingerprint[:12]}",
            column_config={"Resultado": st.column_config.SelectboxColumn("Resultado", options=list(STATUS_VALUES), required=True)},
        )
        submitted = st.form_submit_button("Salvar verificações manuais")
    if not submitted:
        return
    invalid = edited.loc[
        edited["Resultado"].isin(("Aprovado", "Reprovado"))
        & edited["Observação"].fillna("").astype(str).str.strip().eq("")
    ]
    if not invalid.empty:
        st.error("Informe uma observação para cada verificação aprovada ou reprovada.")
        return
    updated = dict(saved)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for row in edited.to_dict("records"):
        status = STATUS_VALUES[row["Resultado"]]
        note = "" if pd.isna(row["Observação"]) else str(row["Observação"]).strip()
        value = {"status": status, "evidence": note if status != "pending" else "Inspeção não registrada."}
        if status != "pending":
            previous = updated.get(row["ID"])
            value["recorded_at"] = (
                previous.get("recorded_at", now)
                if previous and previous.get("status") == status and previous.get("evidence") == note
                else now
            )
        updated[row["ID"]] = value
    st.session_state.validation_manual = updated
    st.success("Evidências manuais registradas nesta sessão.")


def _pitch_prompt(facts: dict, template: str) -> str:
    return f"""Escreva um roteiro oral em português de 260 a 350 palavras, para
2 a 3 minutos de apresentação do TestingStudio Web. Siga a ordem: problema,
solução, demonstração, evidências e pendências. Preserve literalmente as duas
respostas da RTM, as contagens, a lacuna do épsilon e o limite do escore de
mutação. Não declare cobertura total quando a matriz responde Não ou Pendente.
Use apenas os fatos abaixo; nenhuma execução Informix deve ser presumida.

Fatos calculados: {json.dumps(facts, ensure_ascii=False)}
Roteiro factual de referência:\n{template}"""


def _pdf_sections(matrix: dict, fingerprint: str, manual: dict[str, dict]) -> list[tuple[str, list[dict]]]:
    summary = [{
        "Tudo o que foi pedido foi coberto?": matrix["forward"],
        "Tudo o que foi testado foi pedido?": matrix["reverse"],
        "Requisitos validados": f"{matrix['validated']}/{matrix['total_requirements']}",
        "Casos executados": matrix["executed_cases"],
        "Versão analisada": fingerprint[:12],
        "Rodada automática": matrix["run_at"] or "não executada",
    }]
    requirements = [{
        "ID": row["id"], "Requisito": row["title"], "Fonte": row["source"],
        "Estado": row["status"], "Casos": ", ".join(row["check_ids"]),
        "Lacuna": row["known_gap"] or "—",
    } for row in matrix["requirements"]]
    cases = [{
        "ID": row["id"], "Caso": row["title"], "Requisitos": ", ".join(row["requirement_ids"]) or "—",
        "Resultado": STATUS_LABELS.get(row["status"], "Executado" if row["status"] == "executed" else row["status"]),
        "Evidência": row["evidence"],
        "Registrado em": manual.get(row["id"], {}).get("recorded_at", "—"),
    } for row in matrix["cases"]]
    return [("Respostas da RTM", summary), ("Especificação e cobertura", requirements), ("Casos de teste e evidências", cases)]


def render_validation_tab(base_dir: Path, source: str, api_key: str, generate_report: Callable[[str, str], str]) -> None:
    fingerprint = project_fingerprint(base_dir)
    if st.session_state.get("validation_fingerprint") != fingerprint:
        for key in ("validation_auto", "validation_manual", "validation_pitch"):
            st.session_state.pop(key, None)
        st.session_state.validation_fingerprint = fingerprint

    st.subheader("Matriz de Rastreabilidade de Requisitos")
    st.caption("Os requisitos do TestingStudio são vinculados a testes e evidências. A divergência dos negativos pertence ao CAD0001 auditado.")
    if st.button("Executar validação", type="primary", key="execute_validation"):
        with st.spinner("Executando a suíte local e os casos de mutação..."):
            st.session_state.validation_auto = run_local_checks(base_dir, source)
        if not st.session_state.validation_auto.get("runner_error"):
            st.success(f"Rodada concluída: {st.session_state.validation_auto['tests_run']} testes locais executados.")
    auto = st.session_state.get("validation_auto")
    if auto:
        if auto.get("runner_error"):
            st.error(f"Não foi possível executar a suíte local: {auto['runner_error']}")
        if auto["mutation_error"]:
            st.error(f"Suíte de mutação: {auto['mutation_error']}")
        with st.expander("Saída da suíte local"):
            st.code(auto["test_log"], language="text", height=220)
    else:
        st.info("Execute a validação para obter evidências automáticas desta versão do projeto.")

    st.subheader("Verificações manuais")
    st.caption("Use Aprovado ou Reprovado somente após conferir o comportamento e descrever a evidência observada.")
    st.caption("Para conferir M07, gere um primeiro PDF desta aba; depois registre a inspeção e gere o roteiro final com a matriz atualizada.")
    _manual_editor(st.session_state.get("validation_manual", {}), fingerprint)
    manual = st.session_state.get("validation_manual", {})
    matrix = evaluate_matrix(auto, manual)

    st.subheader("Respostas da validação")
    first, second, third = st.columns(3)
    first.metric("Tudo o que foi pedido foi coberto?", matrix["forward"])
    second.metric("Tudo o que foi testado foi pedido?", matrix["reverse"])
    third.metric("Requisitos validados", f"{matrix['validated']}/{matrix['total_requirements']}")
    st.caption("A primeira resposta exige verificações aprovadas e ausência de lacunas. A segunda considera os casos efetivamente executados e seus vínculos.")

    st.subheader("Especificação → Validação")
    requirement_rows = [{
        "ID": row["id"], "Requisito": row["title"], "Critério": row["criterion"],
        "Origem": row["source"], "Casos": ", ".join(row["check_ids"]), "Estado": row["status"],
        "Pendência conhecida": row["known_gap"],
    } for row in matrix["requirements"]]
    st.dataframe(pd.DataFrame(requirement_rows), hide_index=True, width="stretch")
    st.subheader("Validação → Especificação")
    case_rows = [{
        "ID": row["id"], "Caso": row["title"], "Requisitos": ", ".join(row["requirement_ids"]) or "Sem vínculo",
        "Tipo": row["kind"], "Resultado": STATUS_LABELS.get(row["status"], "Executado" if row["status"] == "executed" else row["status"]),
        "Evidência": row["evidence"],
    } for row in matrix["cases"]]
    st.dataframe(pd.DataFrame(case_rows), hide_index=True, width="stretch")
    if matrix["gaps"]:
        st.warning("Pendências identificadas: " + ", ".join(f"{row['id']} ({row['status']})" for row in matrix["gaps"]))

    st.subheader("Pitch do trabalho")
    facts = pitch_facts(matrix)
    digest = snapshot_digest(matrix)
    pitch = st.session_state.get("validation_pitch")
    if pitch and pitch["digest"] != digest:
        st.session_state.pop("validation_pitch", None)
        pitch = None
        st.info("A matriz mudou. Gere um roteiro atualizado para refletir as novas evidências.")
    if st.button("Gerar roteiro do pitch", disabled=auto is None, key="generate_pitch"):
        template = build_pitch_template(facts)
        suggested = ""
        if api_key:
            try:
                with st.spinner("Redigindo o pitch com Gemini..."):
                    suggested = generate_report(_pitch_prompt(facts, template), api_key)
            except Exception as error:
                st.info(f"Gemini não respondeu; roteiro factual disponível. Detalhe: {error}")
        st.session_state.validation_pitch = {"text": template, "suggested": suggested, "digest": digest}
        pitch = st.session_state.validation_pitch
    if pitch:
        st.caption("Roteiro factual baseado na matriz exibida acima.")
        st.markdown(pitch["text"])
        if pitch["suggested"]:
            with st.expander("Versão sugerida pelo Gemini para revisão"):
                st.markdown(pitch["suggested"])
        try:
            script = pitch["text"] + ("\n\n## Versão sugerida pelo Gemini para revisão\n\n" + pitch["suggested"] if pitch["suggested"] else "")
            pdf = create_pdf(
                "Sprint 4 — Pitch e Validação", _pdf_sections(matrix, fingerprint, manual),
                script, report_heading="Roteiro do pitch",
            )
        except Exception as error:
            st.error(f"Não foi possível preparar o PDF da Sprint 4: {error}")
        else:
            st.download_button("Gerar PDF da Sprint 4", data=pdf, file_name="testingstudio_sprint4_pitch_validacao.pdf", mime="application/pdf", key="pdf_validation", on_click="ignore")
    else:
        st.caption("O roteiro e o PDF ficam disponíveis após executar a validação e gerar o pitch.")
