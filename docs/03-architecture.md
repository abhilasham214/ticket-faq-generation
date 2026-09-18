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
        │  - TF-IDF + KMeans        │
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

## Tech stack and why

- **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** — chosen because the goal was to demonstrate a proper frontend, not a notebook. shadcn/ui gives accessible primitives (Card, Badge, Collapsible, Alert) without a heavy component-library dependency.
- **FastAPI, as a Vercel Python serverless function** — Python was the natural choice for the clustering step (scikit-learn), and FastAPI gives typed request/response models (Pydantic) essentially for free, which pays off directly in the Postman/pytest contract tests.
- **No database** — at demo scale (one CSV, one generate call), there's nothing that needs to outlive a single request. Skipping persistence removes an entire class of setup (provisioning, migrations, connection pooling under serverless cold starts) for no loss of functionality the brief asked for.
- **scikit-learn (TF-IDF + KMeans)** — deliberately *not* an LLM call for clustering. At 15-20 tickets, TF-IDF + KMeans with a silhouette-score-based choice of k is cheap, deterministic, and testable; an LLM would be non-deterministic and harder to unit test.
- **Gemini (`google-genai`)** — used only where an LLM adds real value: turning a cluster of raw ticket text into a well-phrased question/answer. Free tier keeps the demo cost-free.

## Components and data flow

1. **Generate** (`POST /api/faqs/generate`, multipart CSV upload): `csv_ingest.py` validates and parses the CSV into ticket rows. `clustering.py` vectorizes all of them with TF-IDF, tries `k` in `[3,5]`, and keeps whichever `k` gets the best silhouette score. For each resulting cluster, `faq_drafting.py` calls Gemini with that cluster's ticket text and top TF-IDF terms, asking for a small JSON object (`theme_title`, `question`, `answer`). The response is assembled and returned directly — nothing is written to disk or a database.
2. **Frontend**: `FaqGenerator` drives the whole flow — pick a CSV, click "Generate FAQs", get clusters back in one round trip; `ClusterCard` renders each theme, with ticket IDs behind a collapsible disclosure.

## Security, scalability, usability tradeoffs (prototype-appropriate)

- **No auth**: acceptable because this is a single-user demo; a real deployment would need at least a login wall before exposing the generate endpoint.
- **CORS is wide open (`allow_origins=["*"]`)**: fine for a same-origin Vercel deployment demo; would be tightened to the actual frontend origin in production.
- **No persistence**: simplest possible design for a stateless demo, at the cost of no result history, no "come back later and see your last run," and no cross-session sharing of generated FAQs. A real product would reintroduce storage once those become requirements.
- **Gemini failure is non-fatal**: every drafting call has a template fallback, so a flaky/rate-limited LLM call degrades FAQ quality rather than breaking the endpoint (see `api/_lib/faq_drafting.py`).
- **CSV upload size**: bounded by Vercel's default request body limit, which is generous for a 15-20 row (or even few-thousand row) CSV but would need chunked/streaming ingestion for very large exports. Larger CSVs also mean a longer synchronous clustering+Gemini pass inside one request, bounded by the serverless function's execution timeout.
