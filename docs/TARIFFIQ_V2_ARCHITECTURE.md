# TariffIQ V2 Architecture

## Vision

TariffIQ is an AI-powered U.S. import tariff classification and duty estimation platform.

The platform converts importer language into HTS classifications, retrieves supporting legal context, calculates duties using deterministic logic, and explains results clearly.

Primary goals:

- Accurate HTS classification
- Deterministic duty calculations
- Auditability
- Low infrastructure cost
- Production readiness
- Scalability through incremental upgrades

---

# Core Principles

## LLM Responsibilities

Allowed:

- Query normalization
- Product understanding
- HTS search term generation
- Explanations
- Summaries

Not Allowed:

- HTS code generation without retrieval
- Tariff rate generation
- Duty calculations
- Compliance decisions

LLMs assist reasoning.

Structured data and deterministic logic make decisions.

---

# V2 System Architecture

## Frontend

Technology:

- Next.js
- TypeScript
- Tailwind CSS

Deployment:

- Vercel

Purpose:

- Landing page
- Authentication
- Search interface
- Search history
- Account management
- Admin upload interface

---

## Backend

Technology:

- FastAPI
- LangGraph

Deployment:

- AWS App Runner

Responsibilities:

- Query API
- Authentication validation
- HTS classification workflow
- Tariff calculation
- Audit logging
- Admin operations

---

## Database

Technology:

- Supabase PostgreSQL

Extensions:

- pgvector

Purpose:

- Users
- Search history
- Query records
- HTS releases
- HTS rates
- Audit logs
- Vector storage

---

## Authentication

Technology:

- Supabase Auth

Providers:

- Google OAuth
- Email Login

Authentication Flow:

User
→ Supabase Auth
→ JWT
→ FastAPI Validation

---

## Storage

Technology:

- AWS S3

Purpose:

- HTS release uploads
- Historical releases
- Backup artifacts
- Manifest files

---

## AI Layer

Technology:

- OpenAI

Purpose:

- Query analysis
- Search term normalization
- Explanation generation

Future:

Provider abstraction should support:

- OpenAI
- Bedrock

without major refactoring.

---

# Service Boundaries

## Query Service

Handles:

- Query execution
- Retrieval
- Classification
- Tariff calculation
- Explanation generation

---

## Authentication Service

Handles:

- Login
- Sessions
- JWT validation

Implemented through Supabase Auth.

---

## Admin Service

Handles:

- HTS uploads
- Release management
- Ingestion monitoring

---

## Ingestion Worker

Handles:

- Parsing
- Chunking
- Embedding
- Index updates

Runs independently of user queries.

---

# Query Pipeline

User Query
→ Query Analyzer
→ HTS Classifier
→ Legal Notes Retrieval
→ Tariff Calculator
→ Response Generator

Outputs:

- HTS Code
- Confidence
- Duty Breakdown
- Legal Notes
- Explanation
- Sources
- Disclaimer

---

# Classification Rules

Classification uses:

- Vector retrieval
- Deterministic ranking
- Confidence thresholds

Low-confidence classifications must escalate.

The system must prefer escalation over hallucination.

---

# Tariff Calculation Rules

Workflow:

Classification
→ HTS Code
→ Exact Rate Lookup
→ Tariff Calculation

Rates must come from authoritative release data.

Rates must never come directly from vector retrieval results.

---

# Legal Notes

Separate retrieval source:

- General Notes
- Section Notes
- Chapter Notes

Purpose:

- Context
- Explanation
- Confidence improvement

Legal notes do not perform calculations.

---

# HTS Release Management

Only one release is active at a time.

States:

- Uploaded
- Processing
- Active
- Failed

Workflow:

Admin Upload
→ S3
→ Parse
→ Chunk
→ Embed
→ Store
→ Activate

Requirements:

- No downtime
- Existing release remains active during processing
- Activation only after successful indexing

---

# Vector Storage

Current:

- Chroma

Target:

- pgvector

Requirement:

Use repository abstraction.

Example:

VectorRepository

Implementations:

- ChromaVectorRepository
- PgVectorRepository

Application logic must not depend directly on storage technology.

---

# Concurrency Strategy

User queries remain synchronous.

No Kafka.

No queue for tariff lookups.

Protection:

- Request rate limits
- LLM concurrency limits
- Retry handling

Implementation:

asyncio.Semaphore

around LLM calls.

---

# Auditability

Every query must record:

- User ID
- HTS Release
- Selected HTS Code
- Confidence
- Retrieval candidates
- Latency
- Model versions
- Timestamp

Purpose:

- Compliance
- Debugging
- Future enterprise requirements

---

# UI Design

Design goals:

- Clean
- Minimal
- Professional
- Fast

Inspiration:

- ChatGPT
- Linear
- Stripe
- Perplexity

---

# Main User Experience

After login:

Sidebar:

- New Search
- History
- Account

Main View:

Chat-style interface

Response Sections:

- HTS Code
- Confidence
- Duty Breakdown
- Legal Notes
- Explanation
- Sources
- Disclaimer

The experience should feel conversational while displaying structured compliance information.

---

# Not Included In V2

Do not build yet:

- Kafka
- OpenSearch
- Kubernetes
- Microservices
- CROSS Ruling ingestion
- Bedrock migration
- Multi-region deployment

These become Phase 2+ features after product validation.

---

# Success Criteria

V2 should:

- Support 50–100 users
- Remain under ~$100/month infrastructure cost
- Produce reliable classifications
- Produce deterministic duty calculations
- Maintain auditability
- Provide a modern SaaS experience
- Be easy to demonstrate to recruiters, users, and investors