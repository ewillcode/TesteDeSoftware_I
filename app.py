"""TestingStudio Web: functional, structural and mutation analysis of CAD0001."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai

from mutation import run_mutation
from pdf_export import create_pdf
from structural import build_all_graphs, def_use_pairs
from validation_ui import render_validation_tab

BASE_DIR = Path(__file__).resolve().parent
SOURCE_FILE = BASE_DIR / "cad0001_item_calculo.txt"
MAX_GENERATION_ATTEMPTS = 4
RETRY_DELAYS_SECONDS = (2, 4, 8)
load_dotenv(BASE_DIR / ".env")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def build_audit_prompt(source: str) -> str:
    return f"""Você é analista de testes de software. Audite em português e Markdown
o CAD0001 por Caixa-Preta. Inclua: tabela PCE para val_param1/2/3 com classes
válidas, inválidas e nulas; AVL com epsilon 0,01 nos pontos On (0,00), Off
(-0,01), Interior (100,00) e Exterior (-100,00); casos com entrada, resultado
segundo o código e justificativa; seção 'Divergência encontrada' comparando
o guia, que espera -1 para negativos, com o fonte real; justificativa de
epsilon 0,01. Não invente validações. Observe o tratamento de NULL.
Fonte:\n~~~text\n{source}\n~~~"""


def boundary_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "Ponto": ["Off", "On", "Interior", "Exterior"],
        "Valor": [-0.01, 0.00, 100.00, -100.00],
        "Condição": ["Primeiro ponto abaixo da fronteira", "Exatamente na fronteira", "Região válida distante da fronteira", "Região negativa distante da fronteira"],
    })


def is_transient_api_error(error: Exception) -> bool:
    return getattr(error, "code", None) in {429, 500, 502, 503, 504}


def generate_report(prompt: str, api_key: str, on_retry: Callable[[int, int], None] | None = None) -> str:
    client = genai.Client(api_key=api_key)
    for attempt in range(MAX_GENERATION_ATTEMPTS):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            report = (response.text or "").strip()
            if not report:
                raise RuntimeError("A API não retornou conteúdo textual para a auditoria.")
            return report
        except Exception as error:
            if not is_transient_api_error(error) or attempt == MAX_GENERATION_ATTEMPTS - 1:
                raise
            delay = RETRY_DELAYS_SECONDS[attempt]
            if on_retry:
                on_retry(attempt + 2, delay)
            time.sleep(delay)
    raise RuntimeError("Não foi possível gerar a auditoria.")


def structural_prompt(source: str, metrics: list[dict], graph_data: list[dict]) -> str:
    return f"""Analise em português e Markdown a Caixa-Branca do CAD0001. Explique o
GFC por função, desvios, caminhos de teste relevantes e V(G). Use exatamente
os nós, arestas e métricas abaixo. Cada função tem uma entrada e uma saída;
V(G)=E-N+2. Não confunda caminhos básicos com casos executados. O fonte não
rejeita valores negativos.
Métricas: {json.dumps(metrics, ensure_ascii=False)}
GFC: {json.dumps(graph_data, ensure_ascii=False)}
Fonte:\n~~~text\n{source}\n~~~"""


def dataflow_prompt(source: str, pairs: list[dict], mutation: dict) -> str:
    payload = {**mutation, "score": str(mutation["score"])}
    return f"""Analise em português e Markdown fluxo de dados e teste de mutação
do CAD0001. Explique os pares Def-Uso por função, p-uso em condições e c-uso
em cálculos/retornos. Origem 'externo' é o estado recebido na função. SQL
define sqlca.sqlcode; não afirme execução Informix. O motor de mutação executa
somente cad0001_calcula_valor numa interpretação Decimal verificada contra o
fonte. Apresente cinco mutantes, casos que os mataram, mortos, sobreviventes e
MS = mortos/(mortos+sobreviventes)*100. O MS é exato para este catálogo e suíte
fixa. Use somente os dados calculados, sem inventar resultados.
Pares: {json.dumps(pairs, ensure_ascii=False)}
Mutação: {json.dumps(payload, ensure_ascii=False)}
Fonte:\n~~~text\n{source}\n~~~"""


def run_gemini_button(label: str, key: str, prompt: str, api_key: str) -> None:
    if not st.button(label, type="primary", key=f"run_{key}"):
        return
    if not api_key:
        st.error("Configure GEMINI_API_KEY no arquivo .env antes de gerar o relatório.")
        return
    notice = st.empty()
    try:
        with st.spinner("Gerando relatório com Gemini..."):
            report = generate_report(prompt, api_key, on_retry=lambda attempt, delay: notice.warning(
                f"A Gemini está temporariamente ocupada. Nova tentativa ({attempt}/{MAX_GENERATION_ATTEMPTS}) em {delay} segundos..."
            ))
        st.session_state[f"report_{key}"] = report
    except Exception as error:
        if is_transient_api_error(error):
            st.error("A Gemini permaneceu indisponível após as tentativas. Tente novamente mais tarde.")
        else:
            st.error(f"Não foi possível gerar o relatório: {error}")
    finally:
        notice.empty()


def pdf_download(key: str, title: str, sections: list[tuple[str, list[dict]]]) -> None:
    st.divider()
    report = st.session_state.get(f"report_{key}")
    if not report:
        st.caption("Gere o relatório com Gemini para liberar o PDF desta aba.")
        st.button("Gerar PDF", key=f"disabled_pdf_{key}", disabled=True)
        return
    try:
        data = create_pdf(title, sections, report)
    except Exception as error:
        st.error(f"Não foi possível preparar o PDF: {error}")
        return
    st.download_button("Gerar PDF", data=data, file_name=f"testingstudio_{key}.pdf", mime="application/pdf", key=f"pdf_{key}", on_click="ignore")


st.set_page_config(page_title="TestingStudio Web — CAD0001", page_icon="🧪", layout="wide")
st.title("🧪 TestingStudio Web — Auditoria do CAD0001")
st.caption("Teste de Software I | Caixa-Preta, Caixa-Branca, Fluxo de Dados, Mutação e Validação")
api_key = os.getenv("GEMINI_API_KEY", "").strip()
with st.sidebar:
    st.header("Autenticação")
    st.success("Chave Gemini configurada pelo arquivo .env.") if api_key else st.error("GEMINI_API_KEY não foi encontrada no arquivo .env.")
    st.caption("A chave nunca é exibida na interface.")

try:
    source_code = SOURCE_FILE.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as error:
    st.error(f"Não foi possível ler {SOURCE_FILE.name}: {error}")
    st.stop()

source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
if st.session_state.get("source_hash") != source_hash:
    for report_key in ("report_blackbox", "report_structural", "report_dataflow"):
        st.session_state.pop(report_key, None)
    st.session_state.source_hash = source_hash

st.subheader("Código-fonte analisado")
st.code(source_code, language="text", line_numbers=True, height=280)
tab_blackbox, tab_structural, tab_dataflow, tab_validation = st.tabs([
    "1 · Caixa-Preta (PCE e AVL)", "2 · Caixa-Branca (GFC e V(G))", "3 · Fluxo de Dados e Mutação", "4 · Pitch e Validação",
])

with tab_blackbox:
    run_gemini_button("Executar Auditoria de Caixa-Preta", "blackbox", build_audit_prompt(source_code), api_key)
    report_tab, boundary_tab = st.tabs(["Relatório PCE e AVL", "Gráfico de Fronteira"])
    with report_tab:
        st.markdown(st.session_state.report_blackbox) if st.session_state.get("report_blackbox") else st.info("Execute a auditoria para gerar o relatório de PCE e AVL.")
    with boundary_tab:
        st.subheader("Pontos de fronteira da AVL")
        st.caption("ε = 0,01 para valores monetários decimais.")
        boundaries = boundary_dataframe()
        st.dataframe(boundaries, hide_index=True, width="stretch")
        st.bar_chart(boundaries, x="Ponto", y="Valor")
        st.warning("O guia considera valores negativos inválidos; o fonte entregue não implementa essa validação.")
    pdf_download("blackbox", "Caixa-Preta — PCE e AVL", [("Pontos de fronteira", boundary_dataframe().to_dict("records"))])

try:
    graphs = build_all_graphs(source_code)
except ValueError as error:
    graphs = []
    graph_error = str(error)

with tab_structural:
    if not graphs:
        st.error(f"Não foi possível mapear o GFC: {graph_error}")
    else:
        metrics = [{"Função": graph.name, "Nós": len(graph.nodes), "Arestas": len(graph.edges), "Decisões": graph.decisions, "V(G)": graph.complexity} for graph in graphs]
        st.subheader("Complexidade ciclomática por função")
        st.dataframe(pd.DataFrame(metrics), hide_index=True, width="stretch")
        selected = st.selectbox("Função para visualizar o GFC", [graph.name for graph in graphs], key="graph_function")
        graph = next(graph for graph in graphs if graph.name == selected)
        st.graphviz_chart(graph.dot(), width="stretch", height=520)
        st.caption(f"{selected}: V(G) = {len(graph.edges)} − {len(graph.nodes)} + 2 = {graph.complexity}; decisões + 1 = {graph.decisions + 1}.")
        with st.expander("Nós e arestas do GFC"):
            st.dataframe(pd.DataFrame([{"Nó": node.id, "Linha": node.line, "Instrução": node.text or node.label} for node in graph.nodes.values()]), hide_index=True, width="stretch")
            st.dataframe(pd.DataFrame([{"Origem": a, "Destino": b, "Ramo": c} for a, b, c in graph.edges]), hide_index=True, width="stretch")
        graph_data = [{"function": item.name, "nodes": [{"id": node.id, "line": node.line, "text": node.text} for node in item.nodes.values()], "edges": item.edges} for item in graphs]
        run_gemini_button("Gerar análise de Caixa-Branca", "structural", structural_prompt(source_code, metrics, graph_data), api_key)
        if st.session_state.get("report_structural"):
            st.markdown(st.session_state.report_structural)
        node_rows = [{"Função": item.name, "Nó": node.id, "Linha": node.line or "—", "Instrução": node.text or node.label} for item in graphs for node in item.nodes.values()]
        edge_rows = [{"Função": item.name, "Origem": a, "Destino": b, "Ramo": c or "—"} for item in graphs for a, b, c in item.edges]
        pdf_download("structural", "Caixa-Branca — GFC e V(G)", [("Métricas", metrics), ("Nós", node_rows), ("Arestas", edge_rows)])

with tab_dataflow:
    if not graphs:
        st.error(f"Não foi possível calcular os pares Def-Uso: {graph_error}")
    else:
        all_pairs = [pair for graph in graphs for pair in def_use_pairs(graph)]
        st.subheader("Pares Def-Uso")
        selected = st.selectbox("Função para visualizar os pares", [graph.name for graph in graphs], key="pair_function")
        visible_pairs = [pair for pair in all_pairs if pair["function"] == selected]
        st.dataframe(pd.DataFrame(visible_pairs).rename(columns={"function": "Função", "variable": "Variável", "definition": "Definição", "definition_line": "Linha def.", "use": "Uso", "use_line": "Linha uso", "kind": "Tipo", "origin": "Origem"}), hide_index=True, width="stretch")
        st.caption("Entrada externa indica estado recebido pela função; os pares são calculados por caminhos sem redefinição.")
        try:
            mutation = run_mutation(source_code)
        except ValueError as error:
            st.error(f"Motor de mutação indisponível: {error}")
            mutation = None
        if mutation:
            st.subheader("Teste de mutação da função de cálculo")
            st.caption("Suíte fixa; execução Decimal da fórmula e do tratamento de NULL verificados no fonte.")
            cases = [{"Caso": case["case"], "p_val1": case["inputs"][0], "p_val2": case["inputs"][1], "p_val3": case["inputs"][2], "Esperado": case["expected"]} for case in mutation["cases"]]
            st.dataframe(pd.DataFrame(cases), hide_index=True, width="stretch")
            mutants = [{"Mutante": row["id"], "Alteração": row["alteration"], "Status": row["status"], "Caso que matou": row["killing_case"], "Original": row["original"], "Mutante (saída)": row["mutant"]} for row in mutation["mutants"]]
            st.dataframe(pd.DataFrame(mutants), hide_index=True, width="stretch")
            st.metric("Escore de Mutação (MS)", f"{mutation['score']:.0f}%")
            st.caption(f"MS = {mutation['killed']} mortos ÷ ({mutation['killed']} mortos + {mutation['survived']} sobreviventes) × 100. Escore limitado aos cinco mutantes e à suíte exibidos.")
            run_gemini_button("Gerar análise de Fluxo de Dados e Mutação", "dataflow", dataflow_prompt(source_code, all_pairs, mutation), api_key)
            if st.session_state.get("report_dataflow"):
                st.markdown(st.session_state.report_dataflow)
            pair_rows = [{"Função": pair["function"], "Variável": pair["variable"], "Definição": f"{pair['definition']} (L{pair['definition_line'] or 'entrada'})", "Uso": f"{pair['use']} (L{pair['use_line']})", "Tipo": pair["kind"], "Origem": pair["origin"]} for pair in all_pairs]
            summary = [{"Mortos": mutation["killed"], "Sobreviventes": mutation["survived"], "MS": f"{mutation['score']:.0f}%"}]
            pdf_download("dataflow", "Fluxo de Dados e Mutação", [("Pares Def-Uso", pair_rows), ("Suíte de teste", cases), ("Mutantes", mutants), ("Escore", summary)])

with tab_validation:
    render_validation_tab(BASE_DIR, source_code, api_key, generate_report)

st.markdown('<hr><p style="text-align:center;color:#6b7280;font-size:0.85rem;">© 2026 Eduardo Will — Todos os direitos reservados.</p>', unsafe_allow_html=True)
