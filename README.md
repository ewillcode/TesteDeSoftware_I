# TestingStudio Web — Sprint 1

Aplicação Web em Streamlit para auditar funcionalmente o programa CAD0001 com
Particionamento em Classes de Equivalência (PCE) e Análise de Valor Limite
(AVL), usando ε = 0,01.

A integração utiliza o modelo Gemini 3.8 Flash.

## Requisitos

- Python 3.10 ou superior
- Uma chave da Gemini API obtida no Google AI Studio

## Instalação e execução

Instale as dependências:

    pip install -r requirements.txt

Copie .env.example para .env e informe a chave:

    GEMINI_API_KEY=sua_chave_aqui

Em seguida, inicie a aplicação:

    streamlit run app.py

O Streamlit exibirá o endereço local, normalmente http://localhost:8501.

## Uso

1. Confirme na barra lateral que a chave foi carregada.
2. Verifique o código de cad0001_item_calculo.txt exibido na página.
3. Selecione Executar Auditoria de Caixa-Preta (PCE & AVL).
4. Consulte a aba de relatório para as classes de equivalência, os limites e os
   casos de teste sugeridos.
5. Consulte o dashboard para os pontos Off (-0,01), On (0,00), Interior
   (100,00) e Exterior (-100,00).

Se a Gemini estiver temporariamente sobrecarregada, a aplicação repetirá a
requisição automaticamente até quatro vezes, com espera progressiva. Se o
serviço continuar indisponível, aguarde alguns instantes e tente novamente.

## Observação sobre a regra de negócio

O guia de laboratório considera números negativos inválidos e cita retorno -1.
O arquivo CAD0001 entregue, porém, converte valores nulos para zero e não contém
essa validação de negativos. A aplicação usa o arquivo real como objeto de
estudo e orienta o Gemini a registrar essa divergência no relatório.

## Segurança

O arquivo .env é ignorado pelo Git. Nunca publique sua chave de API em código,
commits ou capturas de tela.
