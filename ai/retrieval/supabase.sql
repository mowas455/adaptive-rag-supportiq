-- SupportIQ vector store (pgvector + hybrid FTS).
-- Run this ONCE in the Supabase SQL editor, or when you want a clean reset.
-- It drops and recreates the table (existing chunks are deleted).
-- After it succeeds, ingest from the laptop:
--   VECTOR_BACKEND=supabase
--   python -m ai.ingestion.embed_and_store
-- You do NOT re-run this file on every ingest.

create extension if not exists vector;

drop function if exists public.match_chunks(vector, int);
drop function if exists public.search_chunks_fts(text, int);
drop table if exists public.supportiq_chunks cascade;

create table public.supportiq_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector(768) not null,
  source_file text,
  doc_type text,
  chunk_index int,
  page int,
  page_width double precision,
  page_height double precision,
  bbox jsonb,
  polygon jsonb,
  polygon_norm jsonb,
  extraction text,
  created_at timestamptz not null default now()
);

create index supportiq_chunks_embedding_idx
  on public.supportiq_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index supportiq_chunks_fts_idx
  on public.supportiq_chunks
  using gin (to_tsvector('english', coalesce(content, '')));

create index supportiq_chunks_source_idx
  on public.supportiq_chunks (source_file, chunk_index);

alter table public.supportiq_chunks enable row level security;
revoke all on public.supportiq_chunks from anon, authenticated;
grant all on public.supportiq_chunks to service_role;

create or replace function public.match_chunks(
  query_embedding vector(768),
  match_count int default 8
)
returns table (
  content text,
  source_file text,
  doc_type text,
  chunk_index int,
  page int,
  page_width double precision,
  page_height double precision,
  bbox jsonb,
  polygon jsonb,
  polygon_norm jsonb,
  extraction text,
  similarity double precision
)
language sql
stable
as $$
  select
    c.content,
    c.source_file,
    c.doc_type,
    c.chunk_index,
    c.page,
    c.page_width,
    c.page_height,
    c.bbox,
    c.polygon,
    c.polygon_norm,
    c.extraction,
    (1 - (c.embedding <=> query_embedding))::double precision as similarity
  from public.supportiq_chunks c
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.search_chunks_fts(
  query_text text,
  match_count int default 8
)
returns table (
  content text,
  source_file text,
  doc_type text,
  chunk_index int,
  page int,
  page_width double precision,
  page_height double precision,
  bbox jsonb,
  polygon jsonb,
  polygon_norm jsonb,
  extraction text,
  rank double precision
)
language sql
stable
as $$
  select
    c.content,
    c.source_file,
    c.doc_type,
    c.chunk_index,
    c.page,
    c.page_width,
    c.page_height,
    c.bbox,
    c.polygon,
    c.polygon_norm,
    c.extraction,
    ts_rank_cd(
      to_tsvector('english', coalesce(c.content, '')),
      websearch_to_tsquery('english', query_text)
    )::double precision as rank
  from public.supportiq_chunks c
  where to_tsvector('english', coalesce(c.content, ''))
        @@ websearch_to_tsquery('english', query_text)
  order by rank desc
  limit match_count;
$$;

grant execute on function public.match_chunks(vector, int) to service_role;
grant execute on function public.search_chunks_fts(text, int) to service_role;
