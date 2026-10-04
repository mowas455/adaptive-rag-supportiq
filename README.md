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

Everything runs on the laptop except optional hosted pieces: Ollama
(`llama3.2` + `nomic-embed-text`), SQLite orders, self-hosted Langfuse, and a
vector index that is either local **Chroma** or **Supabase pgvector**. The
product UI is the React console.

Onboarding (problem, pipelines, graph, citations, tokens):
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

## Prerequisites

- Python 3.12
- Node.js + npm (frontend)
- [Ollama](https://ollama.com) with `llama3.2:latest` and `nomic-embed-text:latest`
  already pulled (`ollama list`)
- Docker Desktop (Langfuse traces)
- Optional: a Supabase project if `VECTOR_BACKEND=supabase`

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama list
```

Lint Python with `ruff check ai backend` (`pyproject.toml`).

## 1. Langfuse

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

Open [http://localhost:3000](http://localhost:3000). Login: `admin@example.com` / `password123`.

The console **does not iframe** Langfuse (login + `X-Frame-Options` block it). It
loads `/traces/{id}` through our API instead. Use **Open full Langfuse UI** for
the hosted page.

Stop Langfuse. There is **no** default `compose.yaml`, so `docker compose down`
alone fails. Always pass the file, from the repo root (not `frontend/`):

```bash
docker compose -f docker-compose.langfuse.yml down
```

## 2. Ingest knowledge base + orders

PDFs in `data/pdfs/` are the knowledge base (page + bbox extract). Markdown
under `data/docs/` is only used to author those PDFs.

```bash
python -m ai.ingestion.make_nexcart_pdfs
python -m ai.ingestion.embed_and_store
python -m ai.router.train   # optional; writes ai/models/router.joblib
```

Or after the API is up: `curl -X POST http://127.0.0.1:8000/ingest`

## Vector store (Chroma or Supabase)

`VECTOR_BACKEND` in `.env` picks the index. Restart uvicorn after you change it.
Embeddings stay local (`nomic-embed-text`, 768-d). Hybrid retrieve is always on:
Chroma uses BM25; Supabase uses pgvector + Postgres full-text, then RRF.

**Chroma (default, laptop)**

```
VECTOR_BACKEND=chroma
```

**Supabase (hosted Postgres + pgvector)**

Connection is **not** the anon/public key. Use the project URL and the
**service_role** secret from Project Settings → API. That key bypasses RLS and
must stay in `.env` on the backend only.

1. Run `ai/retrieval/supabase.sql` once in the SQL editor (drops and recreates the table + hybrid RPCs). Do not re-run it on every ingest.
2. In `.env`:

```
VECTOR_BACKEND=supabase
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...   # service_role, never anon
```

3. `pip install -r requirements.txt`
4. Ingest again so rows land in `supportiq_chunks`: `python -m ai.ingestion.embed_and_store`
5. Restart the API.

Switch back with `VECTOR_BACKEND=chroma` and restart. Each backend has its own copy of the index; changing the flag does not migrate vectors automatically.

## 3. Backend API

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

There is no `src/` package. `uvicorn src.api.main:app` will fail with
`No module named 'src'`.

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
python -m ai.eval.run_eval
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
frontend/                 product console (React + Vite)
backend/                  FastAPI (/chat /ingest /health /pdf-preview /traces)
ai/                       RAG library
  graph/                  LangGraph nodes and wiring
  ingestion/              PDF extract, preview, embed, seed orders
  retrieval/              hybrid BM25 or pgvector+FTS
  retrieval/supabase.sql  one-time Supabase schema + RPCs
  router/                 heuristic + sklearn + LLM fallback
  models/                 trained router.joblib
  eval/                   golden set, router labels, eval runner
  observability/          Langfuse + token accounting
  tools/                  SQLite orders, web search
data/pdfs/                knowledge-base PDFs
data/docs/                markdown used only to author the PDFs
data/chroma/              Chroma index (gitignored, created at ingest)
docs/                     how the system works
```
