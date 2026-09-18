# Knowledge Base FAQ Auto Builder

Upload resolved support tickets, cluster them into recurring issue themes (TF-IDF + cosine-similarity clustering, no LLM involved), and draft a practical FAQ entry per theme with Gemini - grounded in the actual ticket resolutions, with full source-ticket traceability per theme.

See `docs/` for the full problem statement, requirements, architecture rationale, build process, and testing strategy.

## Stack

- **Frontend**: Next.js (App Router, TypeScript) + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI, deployed as a Vercel Python serverless function (`api/index.py`)
- **Storage**: no database. Each generate call parses, clusters, and drafts in one pass. A few narrow exceptions live in Vercel KV: user-approved custom categories, a seeded demo ticket set for the "Try sample data" button, and the most recently generated result so a fresh visit shows what was last generated instead of an empty page (see `docs/03-architecture.md`).
- **Clustering**: TF-IDF + cosine similarity via scikit-learn's agglomerative clustering (average linkage, fixed distance threshold - no chosen cluster count), boosted by a small curated support-domain keyword taxonomy so same-topic tickets with different wording still group together
- **Cluster naming**: deterministic, rule-based (same domain taxonomy) - no LLM
- **FAQ drafting**: Gemini (`google-genai`), a single batched call for all clusters in one generate request, with a deterministic template fallback - the only place an LLM is used

## Project layout

```
app/                  Next.js pages (App Router)
components/           FaqGenerator, ClusterCard, shadcn/ui primitives
lib/api.ts            Typed fetch wrapper for the backend API
api/index.py          FastAPI app - the single POST /api/faqs/generate route (+ /api/health)
api/_lib/             schemas, csv_ingest, clustering, cluster_naming, domain_categories,
                      text_preprocessing, faq_drafting
data/sample_tickets.csv   20 synthetic resolved tickets for the demo
tests/unit/           Isolated module tests (Gemini mocked)
tests/integration/    FastAPI TestClient, full request/response cycle
tests/api/            Black-box smoke tests against a running instance (BASE_URL)
postman/              Postman collection + environment (functional/negative/edge)
docs/                 Problem, requirements, architecture, process, testing write-ups
```

## Local development

Two supported ways to run it locally:

### Option A - `next dev` + `uvicorn` (no Vercel login required)

Requires **Python 3.10+** (the `google-genai` package uses type-hint syntax that fails to import on 3.9). If your default `python` resolves to an older version, point the venv creation at a newer interpreter explicitly (e.g. `py -3.13 -m venv .venv` on Windows with the Python Launcher, or `python3.11 -m venv .venv` on macOS/Linux).

```bash
npm install
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

# terminal 1
uvicorn api.index:app --reload --port 8000 --env-file .env.local   # --env-file is optional, only needed for GEMINI_API_KEY

# terminal 2
npm run dev
```

Open http://localhost:3000. `next.config.ts` proxies `/api/*` to `http://127.0.0.1:8000` automatically when not running on Vercel. No database or extra setup is required. Without `GEMINI_API_KEY` set, FAQ drafting falls back to a deterministic template instead of calling Gemini.

### Option B - `vercel dev` (matches production routing exactly)

```bash
npm install -g vercel   # or use npx vercel
vercel login
vercel link
vercel env pull .env.local
vercel dev
```

### First run through the app

1. Open the app - it loads `GET /api/faqs/latest` automatically, so the 5-theme sample result (or whatever was last generated, if you've already used the app before) is showing before you upload anything.
2. Confirm the summary bar reads "20 Tickets | 5 Themes | 5 FAQs", and the 5 theme tabs are: *Password Reset & Account Recovery*, *Billing & Duplicate Charge Issues*, *API Authentication & Rate Limit Issues*, *Data Export & Import Issues*, and *Email & Notification Delivery Issues*. Click between tabs - each shows that theme's keyword badges, a grounded Q&A with numbered resolution steps, and a "Show source tickets" disclosure listing its 4 contributing tickets.
3. Upload your own CSV (or `data/sample_tickets.csv` again) and click "Generate FAQs" - the new result replaces the tabs, and becomes what loads on the next visit.

## CSV format

Required columns (case-insensitive): an identifier (`id`, `ticket_id`, or `external_id`), a title (`subject` or `title`), and `resolution`. `description` is optional supporting context. Rows missing any required value are skipped; at least 3 usable tickets are required overall so there's enough signal to detect a recurring theme. See `data/sample_tickets.csv` for a working example.

## Environment variables

See `.env.example`. `GEMINI_API_KEY` (get one at https://aistudio.google.com/apikey) enables real FAQ drafting; without it, FAQ drafting uses a deterministic template.

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
2. `vercel env add GEMINI_API_KEY` (paste your key).
3. `vercel --prod`, or push to the connected GitHub repo's `main` branch for auto-deploy.
