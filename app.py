"""TestingStudio Web — auditoria de Caixa-Preta do programa CAD0001."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent
SOURCE_FILE = BASE_DIR / "cad0001_item_calculo.txt"
MODEL_NAME = "gemini-3.8-flash"
MAX_GENERATION_ATTEMPTS = 4
RETRY_DELAYS_SECONDS = (2, 4, 8)

load_dotenv(BASE_DIR / ".env")


@st.cache_data
def read_source() -> str:
    return SOURCE_FILE.read_text(encoding="utf-8")


def build_audit_prompt(source_code: str) -> str:
    return f"""
Você é um analista de testes de software. Faça uma auditoria funcional de
Caixa-Preta do programa CAD0001 abaixo. Responda em português, usando Markdown.

O relatório deve conter obrigatoriamente:
1. Uma tabela de Particionamento em Classes de Equivalência (PCE) para
   val_param1, val_param2 e val_param3, com entradas válidas, inválidas e nulas.
2. Uma Análise de Valor Limite (AVL) usando epsilon = 0,01 para os pontos
   On (0,00), Off (-0,01), Interior (100,00) e Exterior (-100,00).
3. Casos de teste sugeridos, com entrada, resultado esperado segundo o código e
   justificativa.
4. Uma seção "Divergência encontrada". O guia didático considera valores
   negativos inválidos e espera retorno -1; verifique se o fonte realmente
   implementa essa regra. Diferencie claramente a expectativa do guia do
   comportamento observado no código.
5. Uma justificativa curta para epsilon = 0,01 em valores monetários decimais.

Não invente validações que não estejam no código. Explique que NULL é convertido
em zero caso o fonte confirme esse comportamento.

Código-fonte CAD0001:
~~~text
{source_code}
~~~
""".strip()


def boundary_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Ponto": ["Off", "On", "Interior", "Exterior"],
            "Valor": [-0.01, 0.00, 100.00, -100.00],
            "Condição": [
                "Primeiro ponto abaixo da fronteira",
                "Exatamente na fronteira",
                "Região válida distante da fronteira",
                "Região negativa distante da fronteira",
            ],
        }
    )


def is_transient_api_error(error: Exception) -> bool:
    """Return whether a request may succeed when repeated shortly."""
    return getattr(error, "code", None) in {429, 500, 502, 503, 504}


def generate_audit(
    source_code: str,
    api_key: str,
    on_retry: Callable[[int, int], None] | None = None,
) -> str:
    """Generate the report, retrying temporary Gemini capacity failures."""
    client = genai.Client(api_key=api_key)
    prompt = build_audit_prompt(source_code)

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            report = (response.text or "").strip()
            if not report:
                raise RuntimeError("A API não retornou conteúdo textual para a auditoria.")
            return report
        except Exception as error:
            is_last_attempt = attempt == MAX_GENERATION_ATTEMPTS - 1
            if not is_transient_api_error(error) or is_last_attempt:
                raise

            delay = RETRY_DELAYS_SECONDS[attempt]
            if on_retry:
                on_retry(attempt + 2, delay)
            time.sleep(delay)

    raise RuntimeError("Não foi possível gerar a auditoria.")


def render_footer() -> None:
    st.markdown(
        """
        <hr>
        <p style="text-align: center; color: #6b7280; font-size: 0.85rem;">
            © 2026 Eduardo Will — Todos os direitos reservados.
        </p>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="TestingStudio Web - Sprint 1",
    page_icon="🧪",
    layout="wide",
)
st.title("🧪 TestingStudio Web — Auditoria do CAD0001")
st.caption("Teste de Software I | Sprint 1 | PCE e AVL")

api_key = os.getenv("GEMINI_API_KEY", "").strip()

with st.sidebar:
    st.header("Autenticação")
    if api_key:
        st.success("Chave Gemini configurada pelo arquivo .env.")
    else:
        st.error("GEMINI_API_KEY não foi encontrada no arquivo .env.")
    st.caption("A chave nunca é exibida nem enviada à interface.")

try:
    source_code = read_source()
except (OSError, UnicodeDecodeError) as error:
    st.error(f"Não foi possível ler {SOURCE_FILE.name}: {error}")
    render_footer()
    st.stop()

st.subheader("Código-fonte analisado")
st.code(source_code, language="text")

if st.button("Executar Auditoria de Caixa-Preta (PCE & AVL)", type="primary"):
    if not api_key:
        st.error("Configure GEMINI_API_KEY no arquivo .env antes de executar a auditoria.")
    else:
        retry_notice = st.empty()
        try:
            with st.spinner("Analisando limites e classes de equivalência com Gemini..."):
                report = generate_audit(
                    source_code,
                    api_key,
                    on_retry=lambda attempt, delay: retry_notice.warning(
                        "A Gemini está temporariamente ocupada. "
                        f"Nova tentativa ({attempt}/{MAX_GENERATION_ATTEMPTS}) em {delay} segundos..."
                    ),
                )
            retry_notice.empty()
            st.session_state.audit_report = report
        except Exception as error:
            if is_transient_api_error(error):
                st.error(
                    "A Gemini permaneceu indisponível após novas tentativas. "
                    "Aguarde alguns instantes e execute a auditoria novamente."
                )
            else:
                st.error(f"Não foi possível executar a auditoria: {error}")

tab_report, tab_dashboard = st.tabs(["📋 Relatório (PCE & AVL)", "📊 Gráfico de Fronteira"])

with tab_report:
    report = st.session_state.get("audit_report")
    if report:
        st.markdown(report)
    else:
        st.info("Execute a auditoria para gerar o relatório de PCE e AVL.")

with tab_dashboard:
    st.subheader("Pontos de fronteira da AVL")
    st.caption("ε = 0,01 para valores monetários decimais.")
    boundaries = boundary_dataframe()
    st.dataframe(boundaries, hide_index=True, width="stretch")
    st.bar_chart(boundaries, x="Ponto", y="Valor")
    st.warning(
        "O guia didático classifica os valores negativos como inválidos. "
        "A auditoria deve confirmar no relatório se o código-fonte fornecido aplica essa regra."
    )

render_footer()
