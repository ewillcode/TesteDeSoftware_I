# TestingStudio Web — CAD0001

Aplicação Streamlit para estudar o programa `cad0001_item_calculo.txt` em três abas:

1. **Caixa-Preta:** PCE, AVL, gráfico de fronteira e relatório Gemini.
2. **Caixa-Branca:** GFC visual por função e V(G) de McCabe calculado a partir de nós e arestas.
3. **Fluxo de Dados e Mutação:** pares Def-Uso por função e execução de cinco mutantes da função de cálculo com escore de mutação.

O código-fonte aparece em uma caixa com rolagem. Cada aba permite baixar um PDF com os dados calculados e o texto do Gemini após a geração do seu relatório.

## Instalação

Use Python 3.10 ou superior:

```powershell
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY`. O modelo padrão é `gemini-2.5-flash`; opcionalmente, defina `GEMINI_MODEL` no `.env` para usar outro modelo disponível em sua conta.

```powershell
streamlit run app.py
```

As métricas estruturais e o resultado da mutação são calculados localmente; a chave Gemini é necessária para os relatórios em linguagem natural e seus PDFs.

## Critérios da análise

- Cada função do fonte forma um GFC conectado com entrada e saída únicas. Os `IF` criam os dois ramos; `RETURN` termina no nó de saída. Para cada função, `V(G) = E - N + 2` e é conferido por `decisões + 1`.
- Os pares Def-Uso são intrafunção e mostram definições que alcançam o uso sem redefinição no caminho. Parâmetros e campos de registro recebidos pela função são marcados como origem de entrada; operações SQL definem `sqlca.sqlcode`. A análise não executa o banco.
- O motor de mutação verifica a estrutura da função `cad0001_calcula_valor` antes de executá-la com `Decimal`. A suíte fixa cobre cada parâmetro `NULL`, cálculo comum e valor negativo. Os cinco mutantes trocam cada valor padrão de `NULL` de zero para um, a multiplicação por soma e a soma final por subtração.
- `MS = mortos / (mortos + sobreviventes) × 100` é exato para esses cinco mutantes e essa suíte. O resultado não afirma cobertura de todos os mutantes possíveis ou execução das rotinas Informix/Logix.
- O guia didático espera erro `-1` para negativos; o fonte entregue não contém essa regra. O relatório deve registrar essa divergência.

## Verificação

```powershell
python -m unittest discover -s tests -v
```

O arquivo `.env` é ignorado pelo Git. Não publique a chave de API.
