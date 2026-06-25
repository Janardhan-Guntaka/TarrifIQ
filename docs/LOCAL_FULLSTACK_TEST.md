# TariffIQ — local full-stack test (before Docker deploy)

## 1. Supabase Google Auth (one-time)

1. [Supabase Dashboard](https://supabase.com/dashboard) → **Authentication** → **Providers** → **Google** → Enable
2. Create [Google OAuth client](https://console.cloud.google.com/apis/credentials) (Web application)
   - Authorized redirect URI: `https://foajphcyejhsafivkhdi.supabase.co/auth/v1/callback`
3. Paste Client ID + Secret into Supabase Google provider settings
4. **Authentication** → **URL Configuration**:
   - **Site URL:** `https://tarrif-iq-one.vercel.app` (or your Vercel production URL)
   - **Redirect URLs** (add both):
     - `http://localhost:3000/auth/callback`
     - `https://tarrif-iq-one.vercel.app/auth/callback`

## 2. Frontend env (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://foajphcyejhsafivkhdi.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key from Supabase API settings>
```

## 3. Backend env (repo root `.env`)

Ensure `SUPABASE_JWT_SECRET` is set (Supabase → Settings → API → JWT Secret).

## 4. Run locally

Terminal 1 — API:
```powershell
cd vanguard-ai
.\.venv\Scripts\activate
python run.py api
```

Terminal 2 — Frontend:
```powershell
cd apps/web
npm install
npm run dev
```

## 5. Test flow

1. http://localhost:3000 — landing page
2. **Get started** → Google sign-in
3. http://localhost:3000/app — classify a product
4. **Refresh** — history loads from `GET /v1/queries`
5. Sign out → returns to landing

## 6. Then deploy

Only after local E2E works:
- `.\infra\apprunner\deploy-minimal.ps1` (API)
- Vercel → `apps/web` + `NEXT_PUBLIC_API_URL` + Supabase redirect URL
