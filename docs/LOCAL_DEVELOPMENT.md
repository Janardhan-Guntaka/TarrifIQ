# TariffIQ V2 — Local Development

## Prerequisites

- Python 3.11+
- Supabase project with PostgreSQL + pgvector enabled
- OpenAI API key
- `.env` at project root (copy from `.env.example`)

## 1. Install dependencies

```powershell
cd vanguard-ai
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
```

Optional: keep legacy scripts working:

```powershell
pip install langgraph
```

## 2. Configure environment

Copy `.env.example` → `.env` and fill secrets. **Never commit `.env`.**

| Variable | Local dev | Cloud (AWS/GitHub) |
|----------|-----------|---------------------|
| `SUPABASE_URL`, keys | Same project | Same — set as GitHub Secrets |
| `SUPABASE_DB_PASSWORD` + `DATABASE_CONNECTION` | Auto-builds Postgres URL | — |
| `DATABASE_URL` | Optional override | **Required** — paste direct URI from Supabase → Connect |
| `CORS_ORIGINS` | `http://localhost:3000` | Add your Vercel URL |

**Find a working DB connection locally:**

```powershell
python scripts/test_db_connection.py
```

**Frontend** (`apps/web`):

```powershell
Copy-Item .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Cloud reference:** `env/cloud.env.example` (GitHub Secrets + App Runner)

Required backend vars:

- `OPENAI_API_KEY`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_PASSWORD` + `DATABASE_CONNECTION` **or** explicit `DATABASE_URL`
- `SUPABASE_JWT_SECRET` — for authenticated routes

## 3. Run database migrations

Already applied on project `tariffiq-prod` via Supabase (tables: `hts_releases`, `hts_nodes`, `hts_embeddings`, `policy_snapshots`, etc.).

To re-run manually in Supabase SQL Editor:

1. `supabase/migrations/001_initial_schema.sql`
2. `supabase/migrations/002_seed_policy_snapshots.sql`

Or with Supabase CLI:

```bash
supabase db push
```

## 4. Ingest HTS data

Register or place raw JSON under `data/raw/hts/`, then:

```powershell
# Parse (if needed)
python ingestion/parse_hts.py --file data/raw/hts/hts_2026HTSRev6.json --release 2026HTSRev6

# Full ingest + activate
python -m backend.scripts.ingest_local --version 2026HTSRev6 --skip-parse --activate
```

Or parse + ingest in one step:

```powershell
python -m backend.scripts.ingest_local --version 2026HTSRev6 --file data/raw/hts/hts_2026HTSRev6.json --activate
```

## 5. Start API

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn backend.api.main:app --reload --port 8000
```

Health: http://localhost:8000/health

## 6. Test classify

```powershell
curl -X POST http://localhost:8000/v1/classify `
  -H "Content-Type: application/json" `
  -d '{"query": "gaming laptop from China", "country": "China", "customs_value": 1200}'
```

## Docker (optional)

```powershell
docker compose -f docker-compose.dev.yml up --build
```

## Architecture notes

- Rates come from `hts_nodes` only (never vector metadata).
- Vectors in `hts_embeddings` are retrieval-only.
- Policies loaded from `policy_snapshots` (seeded in migration 002).
- All application code lives under `backend/`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `No active HTS release` | Run ingest with `--activate` |
| `DATABASE_URL is not set` | Add to `.env` |
| pgvector extension missing | Enable in Supabase dashboard |
| JWT 503 on `/v1/queries` | Set `SUPABASE_JWT_SECRET` or use `/v1/classify` without auth |
