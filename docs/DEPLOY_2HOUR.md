# TariffIQ — 2-hour deploy (local → GitHub → AWS → Vercel)

Goal: working classify flow locally, public UI on Vercel, API on AWS App Runner.

## Timeline (≈120 min)

| Step | Time | What |
|------|------|------|
| 1 | 15 min | Supabase migrations + `.env` |
| 2 | 30–45 min | HTS ingest (embeddings) |
| 3 | 10 min | Local API + Next.js smoke test |
| 4 | 15 min | Push to GitHub |
| 5 | 25 min | AWS ECR + App Runner |
| 6 | 10 min | Vercel frontend |

---

## 1. Local backend (required first)

### Supabase

1. [Supabase Dashboard](https://supabase.com/dashboard) → SQL → run:
   - `supabase/migrations/001_initial_schema.sql`
   - `supabase/migrations/002_seed_policy_snapshots.sql`
2. Enable **pgvector** if not already (migration includes `CREATE EXTENSION`).

### Environment

From repo root:

```powershell
Copy-Item .env.example .env
# Edit .env: OPENAI_API_KEY, SUPABASE_*, DATABASE_URL
```

### HTS data + ingest

1. Download HTS JSON from USITC → `data/raw/hts/hts_2026HTSRev6.json`
2. Install deps and ingest:

```powershell
pip install -r backend/requirements.txt
python -m backend.scripts.ingest_local --version 2026HTSRev6 --file data/raw/hts/hts_2026HTSRev6.json --activate
```

### Run API

```powershell
python run.py api
```

- Health: http://localhost:8000/health (needs `active_release`)
- Classify: `POST http://localhost:8000/v1/classify` with `{"query":"gaming laptop from China","country":"China","customs_value":1200}`

Or CLI:

```powershell
python run.py classify "gaming laptop from China"
```

---

## 2. Local frontend

```powershell
cd apps/web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 — should call API at `http://localhost:8000`.

---

## 3. Push to GitHub

```powershell
git add .
git commit -m "Add Next.js UI and App Runner deploy workflow"
git push origin main
```

Remote: `github.com:Janardhan-Guntaka/TarrifIQ.git`

---

## 4. AWS App Runner (API)

### One-time AWS setup

Replace `ACCOUNT_ID` and region as needed (`us-east-1`).

```powershell
# ECR repository
aws ecr create-repository --repository-name tariffiq-api --region us-east-1

# IAM role for App Runner to pull from ECR
aws iam create-role --role-name AppRunnerECRAccessRole --assume-role-policy-document file://infra/apprunner/trust-policy.json
aws iam attach-role-policy --role-name AppRunnerECRAccessRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

Build and push first image locally (or wait for GitHub Action):

```powershell
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker build -f docker/Dockerfile -t ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/tariffiq-api:latest .
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/tariffiq-api:latest
```

Create App Runner service (console is fastest for first time):

1. **App Runner** → Create service → **Container registry** → Amazon ECR → `tariffiq-api:latest`
2. Port **8000**, health check path **`/health`**
3. Add env vars (same as `.env`): `DATABASE_URL`, `OPENAI_API_KEY`, `SUPABASE_*`, `ENVIRONMENT=production`
4. Set `CORS_ORIGINS` to your Vercel URL (add after step 5), e.g. `https://tariffiq.vercel.app,http://localhost:3000`
5. Copy **Service ARN** → GitHub repo **Settings → Secrets and variables → Actions**

### GitHub secrets & variables

**Secrets:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`

**Variables:** `AWS_REGION=us-east-1`, `ECR_REPOSITORY=tariffiq-api`, `APP_RUNNER_SERVICE_ARN=arn:aws:apprunner:...`, `CORS_ORIGINS=https://YOUR-VERCEL-URL.vercel.app,http://localhost:3000`

Run workflow: **Actions → Deploy App Runner → Run workflow**

Note the App Runner URL: `https://xxxxx.us-east-1.awsapprunner.com`

---

## 5. Vercel (public UI)

1. [vercel.com](https://vercel.com) → **Add New Project** → import `TarrifIQ` repo
2. **Root Directory:** `apps/web`
3. **Environment variable:** `NEXT_PUBLIC_API_URL` = App Runner URL (no trailing slash)
4. Deploy

Your public link: `https://<project>.vercel.app`

After deploy, update GitHub `CORS_ORIGINS` and re-run **Deploy App Runner** so the API accepts browser requests from Vercel.

---

## Quick verification checklist

- [ ] `GET {API}/health` → `status: ok`, `active_release` set
- [ ] `POST {API}/v1/classify` returns HTS + duty
- [ ] Vercel UI loads and classifies without CORS errors
- [ ] GitHub Actions deploy succeeds

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Health shows no active release | Re-run ingest with `--activate` |
| CORS error in browser | Add Vercel URL to `CORS_ORIGINS`, redeploy API |
| App Runner unhealthy | Check CloudWatch logs; verify `DATABASE_URL` from App Runner network (Supabase allows all IPs by default) |
| OpenAI errors | Confirm `OPENAI_API_KEY` and billing |
