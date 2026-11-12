# Dashboard ENEM & Estude

Este projeto lê automaticamente todos os arquivos CSV do diretório e monta um dashboard interativo para explorar os dados do ENEM.

## Estrutura do projeto

- [CSV](CSV) — arquivos CSV em lote
- [debug](debug) — scripts de diagnóstico, testes e arquivos temporários
- [app.py](app.py) — dashboard principal
- [requirements.txt](requirements.txt) — dependências

## Como rodar

1. Entre na pasta do projeto.
2. Instale as dependências:
   ```bash
   py -m pip install -r requirements.txt
   ```
3. Inicie o dashboard:
   ```bash
   py -m streamlit run app.py --server.headless true --server.port 8504
   ```

## Funcionalidades

- leitura automática de todos os CSVs
- filtros por ano, UF e sexo
- métricas resumidas
- gráficos de evolução e distribuição
- tabela com os dados filtrados
- botão para exportar o CSV filtrado

## Observação

Os arquivos CSV do ENEM podem ter nomes e colunas diferentes entre anos. O código tenta identificar automaticamente as colunas relevantes e criar uma base unificada para análise.
