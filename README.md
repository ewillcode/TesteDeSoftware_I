# TestingStudio Web — CAD0001

Aplicação Streamlit para estudar o programa `cad0001_item_calculo.txt` em quatro abas:

1. **Caixa-Preta:** PCE, AVL, gráfico de fronteira e relatório Gemini.
2. **Caixa-Branca:** GFC visual por função e V(G) de McCabe calculado a partir de nós e arestas.
3. **Fluxo de Dados e Mutação:** pares Def-Uso por função e execução de cinco mutantes da função de cálculo com escore de mutação.
4. **Pitch e Validação:** matriz bidirecional entre requisitos e casos de teste, evidências, roteiro de apresentação e PDF.

O código-fonte aparece em uma caixa com rolagem. Cada aba permite baixar um PDF com os dados calculados e o texto do Gemini após a geração do seu relatório.

## Instalação

Use Python 3.10 ou superior:

```powershell
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY`. O modelo padrão é `gemini-3.8-flash`; opcionalmente, defina `GEMINI_MODEL` no `.env` para usar outro modelo disponível em sua conta.

```powershell
streamlit run app.py
```

As métricas estruturais e o resultado da mutação são calculados localmente. A chave Gemini é necessária para os relatórios e PDFs das três primeiras abas; o roteiro factual e o PDF da quarta aba funcionam sem ela.

## Sprint 4: Pitch e Validação

Na quarta aba, selecione **Executar validação** para rodar a suíte local e os cinco casos da mutação. Registre na tabela as verificações visuais e da API Gemini como pendentes, aprovadas ou reprovadas; uma conclusão exige observação. A matriz responde:

- **Tudo o que foi pedido foi coberto?** Só responde `Sim` quando todos os requisitos têm verificações aprovadas e não há lacunas conhecidas.
- **Tudo o que foi testado foi pedido?** Verifica se todos os casos executados estão ligados a algum requisito. Um teste novo sem vínculo aparece como extra.

Depois, selecione **Gerar roteiro do pitch**. O roteiro factual usa o retrato da matriz; quando Gemini está disponível, sua versão aparece separadamente para revisão. O PDF reúne respostas, requisitos, casos, evidências e roteiro. Evidências manuais e resultados da rodada ficam nesta sessão e são invalidados quando o código ou os testes mudam.

Para registrar a inspeção do PDF da própria Sprint 4 (M07), gere e confira um primeiro PDF, salve a observação manual e gere novamente o roteiro final. A aba avisa quando uma evidência nova torna o roteiro anterior desatualizado.

A matriz registra como lacuna o ε fixo em `0,01`, pois o kickoff pede seu cálculo a partir da escala decimal. Ela mantém a divergência dos negativos como achado sobre o programa CAD0001, sem tratá-la como uma regra implementada no fonte.

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
