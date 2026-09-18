# Architecture

## Overview

```
        ┌───────────────────────────┐
        │   Next.js UI (Vercel)     │
        │  TypeScript + Tailwind    │
        │  + shadcn/ui              │
        └─────────────┬─────────────┘
                       │ /api/*
                       ▼
        ┌───────────────────────────┐
        │  FastAPI on Vercel Python │
        │  serverless function      │
        │  (api/index.py)           │
        │  - CSV parse              │
        │  - TF-IDF + cosine sim.   │
        │    clustering + naming    │
        │  - Gemini FAQ drafting    │
        └─────────────┬─────────────┘
                       │
                       ▼
                ┌──────────────┐
                │ Gemini API   │
                │ (FAQ drafts) │
                └──────────────┘
```

One Vercel project hosts both halves. `vercel.json` rewrites `/api/(.*)` to the Python function (`api/index.py`); everything else is served by Next.js. Locally, `next dev` alone doesn't run the Python function, so `next.config.ts` proxies `/api/*` to a separately-run `uvicorn` process in that mode (see `docs/04-process.md` and the README) — on Vercel itself, `vercel.json`'s rewrite wins before Next.js ever sees the request.

The app is stateless: there is no database. A single request (`POST /api/faqs/generate`, CSV in) does parsing, clustering, and FAQ drafting in one pass and returns everything the UI needs. Nothing is persisted server-side, so there's no upload/generate/fetch split and no reload-keeps-last-result behavior — results live only in the browser tab until you generate again.

Two narrow exceptions, both backed by Vercel KV (`api/_lib/kv_store.py`) rather than a database, because each is one small, explicit piece of state a human decision needs to survive across requests - not general persistence brought back "just in case": `category_store.py` (a user-approved "new domain" from the frontend popup, so future uploads recognize it automatically - see `POST /api/categories`) and `ticket_store.py` (a seeded demo ticket set, so the app has something to show via `POST /api/faqs/generate/sample` without requiring a CSV upload first). Both degrade gracefully with no KV configured - custom categories are just absent, and the sample set falls back to reading the bundled `data/sample_tickets.csv` fresh each call.

## Tech stack and why

- **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** — chosen because the goal was to demonstrate a proper frontend, not a notebook. shadcn/ui gives accessible primitives (Card, Badge, Collapsible, Alert) without a heavy component-library dependency.
- **FastAPI, as a Vercel Python serverless function** — Python was the natural choice for the clustering step (scikit-learn), and FastAPI gives typed request/response models (Pydantic) essentially for free, which pays off directly in the Postman/pytest contract tests.
- **No database** — at demo scale (one CSV, one generate call), there's nothing that needs to outlive a single request. Skipping persistence removes an entire class of setup (provisioning, migrations, connection pooling under serverless cold starts) for no loss of functionality the brief asked for. The two exceptions (`category_store.py`, `ticket_store.py`) use Vercel KV specifically because it's a REST call, not a connection pool - no migrations, no schema, nothing that needs to survive a serverless cold start beyond a key's current value.
- **TF-IDF + cosine similarity, not KMeans** — the first version picked a cluster count `k` in `[3,5]` via silhouette score, which forces every ticket into one of a fixed number of buckets even when the data doesn't actually split that way (it was visibly wrong: an SSO ticket and an unsubscribe-link ticket landed in the same cluster because *some* k needed a home for both). The current approach never chooses a `k` up front - see `api/_lib/clustering.py`.
- **Domain-category keyword tagging** — plain TF-IDF on short, differently-worded tickets is sparse: two tickets about the same real-world issue ("card declined" vs. "duplicate invoice charge") often share almost no literal words. `api/_lib/domain_categories.py` is a small curated keyword taxonomy (auth, billing, api, data, email) used to tag matching tickets with a synthetic shared token before vectorizing - still plain keyword matching, not an embedding model, but it bridges vocabulary gaps within the same support domain. Tuning notes and the empirical case for this are in `clustering.py`'s module docstring.
- **Rule-based cluster naming, no LLM** — `api/_lib/cluster_naming.py` names a cluster from its own top TF-IDF terms via the same domain taxonomy plus a few sub-rules, so a name like "Billing & Duplicate Charge Issues" is always traceable to specific words that were actually present, never a model's guess.
- **Gemini (`google-genai`)** — used for exactly one job: drafting the FAQ (question, answer, resolution steps, escalation guidance) for an already-formed, already-named cluster. Free tier keeps the demo cost-free.

## Components and data flow

1. **Generate** (`POST /api/faqs/generate`, multipart CSV upload):
   - `csv_ingest.py` validates and parses the CSV into ticket rows (requires an id, a subject/title, and a resolution per row; at least 3 usable tickets total).
   - `clustering.py` builds a TF-IDF matrix (title weighted 2x, resolution 1x, matched domain-category tags repeated as a bridging signal), then runs cosine-distance agglomerative clustering with *average* linkage and a fixed distance threshold - clusters emerge from the similarity structure, not a chosen count. Every cluster carries its member tickets, top keywords, and similarity diagnostics.
   - `cluster_naming.py` turns each cluster's top keywords into a human-readable theme name via the same domain taxonomy - fully deterministic, no LLM involved.
   - `faq_drafting.py` makes a single Gemini call for the whole batch, with every cluster's theme, keywords, and member tickets' title/description/resolution in one prompt, asking for a JSON array of `{cluster_index, question, answer, resolution_steps, escalation}` objects (one per cluster, matched back up by `cluster_index`). Batching avoids making N separate Gemini requests per generate call, which was easy to rate-limit on the free API tier. The response is validated per-entry; any failure (no API key, network error, malformed JSON, wrong entry count, a bad `cluster_index`, missing fields) falls back to a deterministic template built from each cluster's own resolutions, for every cluster in the batch.
   - The response is assembled and returned directly - nothing is written to disk or a database.
2. **Sample data** (`POST /api/faqs/generate/sample`, no body): the "Try sample data" button runs through the exact same pipeline as step 1, sourced from `ticket_store.get_seeded_tickets()` instead of an uploaded CSV - so the app has something to show on first load. That function reads the seed set from Vercel KV if present, otherwise reads the bundled `data/sample_tickets.csv` directly (and opportunistically writes it to KV for next time).
3. **Frontend**: `FaqGenerator` drives the whole flow - pick a CSV (or click "Try sample data"), click "Generate FAQs", get clusters back in one round trip; `ClusterCard` renders each theme's keywords, FAQ, numbered resolution steps, and escalation guidance, with the full list of source tickets (id, title, resolution) behind a "Show source tickets" disclosure for traceability.

## Security, scalability, usability tradeoffs (prototype-appropriate)

- **No auth**: acceptable because this is a single-user demo; a real deployment would need at least a login wall before exposing the generate endpoint.
- **CORS is wide open (`allow_origins=["*"]`)**: fine for a same-origin Vercel deployment demo; would be tightened to the actual frontend origin in production.
- **No persistence**: simplest possible design for a stateless demo, at the cost of no result history, no "come back later and see your last run," and no cross-session sharing of generated FAQs. A real product would reintroduce storage once those become requirements.
- **Gemini failure is non-fatal**: every drafting call has a template fallback, so a flaky/rate-limited LLM call degrades FAQ quality rather than breaking the endpoint (see `api/_lib/faq_drafting.py`).
- **CSV upload size**: bounded by Vercel's default request body limit, which is generous for a 15-20 row (or even few-thousand row) CSV but would need chunked/streaming ingestion for very large exports. Larger CSVs also mean a longer synchronous clustering+Gemini pass inside one request, bounded by the serverless function's execution timeout.
