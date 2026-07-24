# Microserviço de Ingestão & Insights com Gemini API

Microserviço em Python 3.11+ utilizando **FastAPI**, **PostgreSQL** (via **SQLAlchemy 2.0 Async** & **asyncpg**), **Pydantic v2** e a nova SDK **`google-genai`** da Google para auditoria automatizada e geração de análises empresariais estruturadas via IA.

---

## 🚀 Arquitetura & Tecnologias

- **Framework Web**: [FastAPI](https://fastapi.tiangolo.com/)
- **ORM & Banco de Dados**: [SQLAlchemy 2.0 Async](https://www.sqlalchemy.org/) com [asyncpg](https://github.com/MagicStack/asyncpg) + PostgreSQL
- **Validação de Dados**: [Pydantic v2](https://docs.pydantic.dev/latest/)
- **Inteligência Artificial**: [Google GenAI SDK](https://pypi.org/project/google-genai/) com **Structured Outputs**
- **Conteinerização**: Docker & Docker Compose
- **Testes Automatizados**: `pytest`, `pytest-asyncio`, `httpx`

---

## 🛠️ Requisitos de Negócio e Endpoints

### 1. Ingestão de Vendas e Auditoria de Anomalias (`POST /api/v1/ingest`)
- Aceita registros via **JSON Body** (objeto ou array) ou **Upload de arquivo CSV**.
- Executa validações estritas (faturamento $\ge 0$, datas válidas).
- **Regra de Auditoria**: Calcula a média de faturamento dos últimos 7 dias gravados para a empresa. Se o faturamento do dia for $\ge 30\%$ menor que a média dos últimos 7 dias, registra um log de auditoria com severidade **`CRITICAL`** na tabela `logs_auditoria`.
- Salva o registro no banco PostgreSQL.

### 2. Geração de Insight Executivo (`POST /api/v1/generate-insight`)
- Recebe `empresa_id` e `data_referencia`.
- Consulta os dados de venda do dia e anomalias registradas na auditoria.
- Invoca a Gemini API via SDK `google-genai` impondo retorno JSON estruturado contendo:
  - `resumo` (string)
  - `alertas_principais` (array de strings)
  - `acao_recomendada` (string)
- Salva o retorno na tabela `insights_diarios` e o devolve na resposta HTTP.

---

## 📋 Como Executar o Projeto

### Opção 1: Execução Local com Python e Virtualenv

1. **Clone/Navegue para a pasta do projeto**:
   ```bash
   cd fastapi_gemini_microservice
   ```

2. **Crie e ative um ambiente virtual**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as Variáveis de Ambiente**:
   Copie `.env.example` para `.env` e preencha a chave do Gemini e do PostgreSQL:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/vendas_db
   GEMINI_API_KEY=sua_chave_gemini_aqui
   GEMINI_MODEL=gemini-2.5-flash
   ```

5. **Inicie o servidor**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. Acesse a documentação interativa OpenAPI (Swagger):
   - `http://localhost:8000/docs`

---

### Opção 2: Deploy com Docker

1. **Construa a imagem Docker**:
   ```bash
   docker build -t fastapi-gemini-ingestion .
   ```

2. **Execute o container**:
   ```bash
   docker run -d -p 8000:8000 --env-file .env fastapi-gemini-ingestion
   ```

---

## 🧪 Execução de Testes Automatizados

Os testes rodam de forma isolada com banco SQLite assíncrono em memória:

```bash
pytest -v
```
