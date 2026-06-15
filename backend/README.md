# TariffIQ V2 Backend

Production path: **FastAPI + LangGraph + Supabase (Postgres/pgvector) + OpenAI**.

## Layout

```
backend/
  api/           FastAPI routes and JWT middleware
  config/        Environment settings
  core/          Types and dependency injection
  db/            Postgres connection pool
  graph/         LangGraph pipeline and nodes
  ingestion/     Hierarchy and legal note helpers
  repositories/  Data access (hts_nodes, pgvector, policy, queries, releases)
  scripts/       CLI: ingest_local, activate_release
  services/      OpenAI embedding/LLM, query orchestration
  tariff/        PolicyEngine + DutyEngine (deterministic)
```

## Rules

1. LLMs never set duty rates.
2. Rates from `hts_nodes` only.
3. `hts_embeddings` for retrieval only.
4. Every `/v1/classify` persists a `queries` audit row.

See [docs/LOCAL_DEVELOPMENT.md](../docs/LOCAL_DEVELOPMENT.md).
