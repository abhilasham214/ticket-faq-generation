# Knowledge Base FAQ Auto Builder

Upload resolved support tickets, cluster them into 3-5 recurring issue themes (TF-IDF + KMeans), and draft a practical FAQ entry per theme with Gemini - grounded in the actual ticket resolutions, with a ticket count per theme.

See `docs/` for the full problem statement, requirements, architecture rationale, build process, and testing strategy.

## Stack

- **Frontend**: Next.js (App Router, TypeScript) + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI, deployed as a Vercel Python serverless function (`api/index.py`)
- **Database**: Vercel Postgres (Neon) via SQLAlchemy
- **Clustering**: scikit-learn (TF-IDF + KMeans, auto-picks k in [3,5] by silhouette score)
- **FAQ drafting**: Gemini (`google-genai`), one call per cluster, with a deterministic template fallback

## Project layout

```
app/                  Next.js pages (App Router)
components/           TicketUpload, ClusterCard, shadcn/ui primitives
lib/api.ts            Typed fetch wrappers for the backend API
api/index.py          FastAPI app - all routes
api/_lib/             db, models, schemas, csv_ingest, clustering, faq_drafting
data/sample_tickets.csv   20 synthetic resolved tickets for the demo
tests/unit/           Isolated module tests (Gemini mocked)
tests/integration/    FastAPI TestClient + throwaway SQLite DB
tests/api/            Black-box smoke tests against a running instance (BASE_URL)
postman/              Postman collection + environment (functional/negative/edge)
docs/                 Problem, requirements, architecture, process, testing write-ups
```

## Local development

Two supported ways to run it locally:

### Option A - `next dev` + `uvicorn` (no Vercel login required)

```bash
npm install
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

# terminal 1
uvicorn api.index:app --reload --port 8000

# terminal 2
npm run dev
```

Open http://localhost:3000. `next.config.ts` proxies `/api/*` to `http://127.0.0.1:8000` automatically when not running on Vercel. Without `POSTGRES_URL` set, the backend falls back to a local SQLite file (`local_dev.db`). Without `GEMINI_API_KEY` set, FAQ drafting falls back to a deterministic template instead of calling Gemini.

### Option B - `vercel dev` (matches production routing exactly)

```bash
npm install -g vercel   # or use npx vercel
vercel login
vercel link
vercel env pull .env.local
vercel dev
```

### First run through the app

1. Open the app, upload `data/sample_tickets.csv`.
2. Click "Generate FAQs".
3. Confirm 3-5 theme cards appear, ticket counts sum to 20, and each FAQ answer reads as grounded in that theme's tickets (login/password, billing, API/rate-limits, data export/import, email/notifications).

## Environment variables

See `.env.example`. `GEMINI_API_KEY` (get one at https://aistudio.google.com/apikey) enables real FAQ drafting; `POSTGRES_URL` points at Vercel Postgres/Neon (omit for local SQLite).

## Testing

```bash
pip install -r requirements.txt   # includes pytest, httpx
pytest                            # unit + integration tests

# with a backend running (see Local development above):
npx newman run postman/ticket-faq-api.postman_collection.json \
  -e postman/ticket-faq-api.postman_environment.json \
  --env-var baseUrl=http://localhost:8000 \
  --working-dir .
```

See `docs/05-testing.md` for the full test matrix and a log of defects actually found and fixed while building this.

## Deployment (Vercel)

1. `vercel login` and `vercel link` to create/link the project.
2. In the Vercel dashboard, add the **Postgres** (Neon) integration to the project - this populates `POSTGRES_URL` automatically.
3. `vercel env add GEMINI_API_KEY` (paste your key).
4. `vercel --prod`, or push to the connected GitHub repo's `main` branch for auto-deploy.
