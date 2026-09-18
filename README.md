# SupportIQ — Adaptive RAG Customer Support Assistant

Local Adaptive RAG system for a fictional mid-size e-commerce company (**NexCart**).
Queries are routed to a vector knowledge base, a SQLite orders table, or web search,
then graded and optionally retried. Everything runs on your laptop: Ollama, Chroma,
SQLite, and self-hosted Langfuse.

## Prerequisites

- Python 3.12
- [Ollama](https://ollama.com) with `llama3.2:latest` and `nomic-embed-text:latest`
  already pulled (`ollama list` — do not pull models in this project)
- Docker Desktop (for Langfuse)

Onboarding (problem, RAG vs Adaptive RAG, every pipeline step, diagrams):

- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

## Setup

```bash
cd /Users/mownieshasokan/adaptive-rag-supportiq
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama list
```

## 1. Langfuse

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

Open [http://localhost:3000](http://localhost:3000). Login: `admin@example.com` / `password123`.

## 2. Ingest knowledge base + orders

```bash
python -m src.ingestion.embed_and_store
```

Or via API after the server is up: `curl -X POST http://127.0.0.1:8000/ingest`

## 3. FastAPI

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

```bash
curl http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What'\''s your return window?","session_id":"demo"}'
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Where is order #4521?","session_id":"demo"}'
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Is there a major UPS outage right now?","session_id":"demo"}'
```

Each `/chat` response includes `source_type`, `retries`, and `trace_url` (open that URL in Langfuse).

## 4. Streamlit UI

With the API already running:

```bash
streamlit run ui/streamlit_app.py
```

## 5. Golden-set eval

```bash
python eval/run_eval.py
```

Prints routing accuracy by branch (`vectorstore` / `sql_lookup` / `web_search`) and writes a pass/fail score onto each Langfuse trace. Takes several minutes (15 local LLM runs).

## Graph (CLI, no API)

```bash
python -m src.graph.build_graph --mermaid
python -m src.graph.build_graph "What's your return window?"
```

Control flow: classify → retrieve/sql/web → grade docs → at most one rewrite+retrieve then web fallback → generate → grade answer (regenerate once, then abstain).

## Repo layout

```
data/docs/                      sample policy / FAQ / manual markdown
src/ingestion/                  loaders, Chroma embed, orders seed
src/graph/                      LangGraph state, nodes, compiled graph
src/tools/                      SQLite order lookup + web search
src/observability/              Langfuse callback + custom scores
src/api/main.py                 FastAPI /ingest /chat /health
ui/streamlit_app.py             chat UI + route badge
eval/golden_qa.json             15 routing questions
eval/run_eval.py
docker-compose.langfuse.yml
```
