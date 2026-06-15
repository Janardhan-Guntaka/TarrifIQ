-- TariffIQ V2 — initial schema
-- Run manually in Supabase SQL Editor or via supabase db push

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- users (profile mirror; auth.users holds credentials)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
    id          UUID PRIMARY KEY,
    email       TEXT NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'free',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- hts_releases
-- ---------------------------------------------------------------------------
CREATE TYPE public.release_status AS ENUM (
    'processing',
    'active',
    'archived',
    'failed'
);

CREATE TABLE IF NOT EXISTS public.hts_releases (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version         TEXT NOT NULL UNIQUE,
    status          public.release_status NOT NULL DEFAULT 'processing',
    effective_date  DATE,
    s3_key          TEXT,
    sha256          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hts_releases_status ON public.hts_releases (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hts_releases_one_active
    ON public.hts_releases (status)
    WHERE status = 'active';

-- ---------------------------------------------------------------------------
-- hts_nodes — authoritative rates and hierarchy (Rule 2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.hts_nodes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id      UUID NOT NULL REFERENCES public.hts_releases (id) ON DELETE CASCADE,
    hts_code        TEXT NOT NULL,
    node_type       TEXT NOT NULL,
    parent_code     TEXT,
    description     TEXT NOT NULL DEFAULT '',
    general_rate    TEXT NOT NULL DEFAULT '',
    special_rate    TEXT NOT NULL DEFAULT '',
    other_rate      TEXT NOT NULL DEFAULT '',
    chapter         TEXT NOT NULL DEFAULT '',
    heading         TEXT NOT NULL DEFAULT '',
    subheading      TEXT NOT NULL DEFAULT '',
    unit_of_qty     TEXT,
    indent_level    SMALLINT,
    CONSTRAINT hts_nodes_release_code_unique UNIQUE (release_id, hts_code),
    CONSTRAINT hts_nodes_node_type_check CHECK (
        node_type IN ('chapter', 'heading', 'subheading', 'tariff_item', 'statistical')
    )
);

CREATE INDEX IF NOT EXISTS idx_hts_nodes_release ON public.hts_nodes (release_id);
CREATE INDEX IF NOT EXISTS idx_hts_nodes_release_code ON public.hts_nodes (release_id, hts_code);
CREATE INDEX IF NOT EXISTS idx_hts_nodes_release_heading ON public.hts_nodes (release_id, heading);
CREATE INDEX IF NOT EXISTS idx_hts_nodes_release_chapter ON public.hts_nodes (release_id, chapter);

-- ---------------------------------------------------------------------------
-- hts_embeddings — pgvector retrieval only (Rule 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.hts_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id      UUID NOT NULL REFERENCES public.hts_releases (id) ON DELETE CASCADE,
    chunk_id        TEXT NOT NULL,
    hts_code        TEXT,
    doc_type        TEXT NOT NULL,
    chunk_text      TEXT NOT NULL,
    embedding       vector(1536) NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT hts_embeddings_release_chunk_unique UNIQUE (release_id, chunk_id),
    CONSTRAINT hts_embeddings_doc_type_check CHECK (
        doc_type IN ('node', 'heading_summary', 'legal_note')
    )
);

CREATE INDEX IF NOT EXISTS idx_hts_embeddings_release ON public.hts_embeddings (release_id);
CREATE INDEX IF NOT EXISTS idx_hts_embeddings_release_doctype ON public.hts_embeddings (release_id, doc_type);
CREATE INDEX IF NOT EXISTS idx_hts_embeddings_hnsw
    ON public.hts_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- policy_snapshots — versioned trade policy (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version         TEXT NOT NULL,
    policy_type     TEXT NOT NULL,
    effective_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    policy_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT policy_snapshots_version_type_unique UNIQUE (version, policy_type),
    CONSTRAINT policy_snapshots_type_check CHECK (
        policy_type IN ('IEEPA', 'SECTION_301', 'FTA')
    )
);

CREATE INDEX IF NOT EXISTS idx_policy_snapshots_type ON public.policy_snapshots (policy_type, effective_date DESC);

-- ---------------------------------------------------------------------------
-- ingestion_runs — GitHub Actions / local ingest status
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ingestion_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id      UUID NOT NULL REFERENCES public.hts_releases (id) ON DELETE CASCADE,
    github_run_id   TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    step            TEXT,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    CONSTRAINT ingestion_runs_status_check CHECK (
        status IN ('pending', 'running', 'completed', 'failed')
    )
);

-- ---------------------------------------------------------------------------
-- queries — audit + history (Rule 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.queries (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID REFERENCES public.users (id) ON DELETE SET NULL,
    raw_query               TEXT NOT NULL,
    country                 TEXT,
    customs_value           NUMERIC(14, 2),
    selected_hts_code       TEXT,
    confidence              NUMERIC(5, 4),
    policy_version          TEXT,
    hts_release             TEXT,
    response_json           JSONB,
    retrieval_candidates    JSONB,
    latency_ms              INTEGER,
    escalate                BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queries_user_created ON public.queries (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_queries_hts_release ON public.queries (hts_release);

-- ---------------------------------------------------------------------------
-- RLS (enable; policies can be tightened per environment)
-- ---------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hts_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hts_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hts_releases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_snapshots ENABLE ROW LEVEL SECURITY;

-- Authenticated users read their own queries
CREATE POLICY queries_select_own ON public.queries
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY queries_insert_own ON public.queries
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Public read for active release data (service role bypasses RLS for ingest)
CREATE POLICY hts_nodes_read ON public.hts_nodes
    FOR SELECT USING (true);

CREATE POLICY hts_embeddings_read ON public.hts_embeddings
    FOR SELECT USING (true);

CREATE POLICY hts_releases_read ON public.hts_releases
    FOR SELECT USING (true);

CREATE POLICY policy_snapshots_read ON public.policy_snapshots
    FOR SELECT USING (true);
