# SupportIQ — Adaptive RAG Customer Support Assistant

Local Adaptive RAG for a fictional mid-size e-commerce company (**NexCart**).
Each question is routed to a vector knowledge base, a SQLite orders table, or
web search, then graded and optionally retried.

Layout is split the way a production app is split:

| Folder | Role |
|---|---|
| `frontend/` | React + Vite console (chat, PDF evidence, observability) |
| `backend/` | FastAPI HTTP surface |
| `ai/` | Ingest, LangGraph, retrieve, router, tools, Langfuse, token usage |
| `src/api/main.py` | Compatibility shim: `uvicorn src.api.main:app` still works |

Everything runs on the laptop: Ollama (`llama3.2` + `nomic-embed-text`), Chroma,
SQLite, and self-hosted Langfuse. Streamlit under `ui/` is leftover, not the product UI.

Onboarding (problem, pipelines, graph, citations, tokens):
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

## Prerequisites

- Python 3.12
- Node.js + npm (frontend)
- [Ollama](https://ollama.com) with `llama3.2:latest` and `nomic-embed-text:latest`
  already pulled (`ollama list`)
- Docker Desktop (Langfuse)

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama list
```

Lint Python with `ruff check ai backend eval` (`pyproject.toml`).

## 1. Langfuse

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

Open [http://localhost:3000](http://localhost:3000). Login: `admin@example.com` / `password123`.

The console **does not iframe** Langfuse (login + `X-Frame-Options` block it). It
loads `/traces/{id}` through our API instead. Use **Open full Langfuse UI** for
the hosted page.

Stop Langfuse (file name is required; there is no default `compose.yaml`):

```bash
docker compose -f docker-compose.langfuse.yml down
```

## 2. Ingest knowledge base + orders

PDFs in `data/pdfs/` are the knowledge base (page + bbox extract). Markdown
under `data/docs/` is only used to author those PDFs.

```bash
python -m ai.ingestion.make_nexcart_pdfs
python -m ai.ingestion.embed_and_store
python -m ai.router.train   # optional; writes models/router.joblib
```

Or after the API is up: `curl -X POST http://127.0.0.1:8000/ingest`

## 3. Backend API

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
curl http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What'\''s your return window?","session_id":"demo"}'
```

`/chat` returns `route`, `citations` (page + polygon), `trace_id` / `trace_url`,
and `usage` for **both** local models:

```json
"usage": {
  "llm": { "model": "llama3.2", "prompt_tokens": 963, "completion_tokens": 90, "total_tokens": 1053, "calls": 3 },
  "embedding": { "model": "nomic-embed-text", "prompt_tokens": 16, "calls": 2 }
}
```

Other routes: `GET /pdf-preview`, `GET /traces/{trace_id}`.

Stop the API (PID, not the port number):

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill
```

## 4. Console UI (React)

With the API running:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to
`http://127.0.0.1:8000`. Three panes: conversation, PDF evidence with highlight,
observability (this-run metrics including llama3.2 + nomic tokens, plus Langfuse
steps/scores).

## 5. Golden-set eval

```bash
python eval/run_eval.py
```

Routing accuracy by branch (`vectorstore` / `sql_lookup` / `web_search`), lexical
`must_contain`, groundedness, citations.

## Graph (CLI, no API)

```bash
python -m ai.graph.build_graph --mermaid
python -m ai.graph.build_graph "What's your return window?"
```

Control flow: classify → retrieve/sql/web → grade docs → at most one
rewrite+retrieve (vectorstore stays on docs; no CRAG web hop) → generate →
grade answer (regenerate once, then abstain).

## Repo layout

```
frontend/                 React console
backend/                  FastAPI
ai/                       RAG pipeline
ai/observability/         Langfuse + per-request token accounting
ai/ingestion/             PDF layout extract, preview PNG, embed
src/api/main.py           shim → backend.main:app
data/pdfs/                NexCart PDFs (ingest source)
data/docs/                markdown used to generate the PDFs
eval/                     golden set
ui/streamlit_app.py       legacy; do not use as the console
```
