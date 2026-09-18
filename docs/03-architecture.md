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
        │  - CSV ingest             │
        │  - TF-IDF + KMeans        │
        │  - Gemini FAQ drafting    │
        └───────┬───────────┬───────┘
                │           │
                ▼           ▼
      ┌──────────────┐  ┌──────────────┐
      │ Vercel        │  │ Gemini API   │
      │ Postgres      │  │ (FAQ drafts) │
      │ (Neon)        │  └──────────────┘
      │ tickets/      │
      │ clusters/faqs │
      └──────────────┘
```

One Vercel project hosts both halves. `vercel.json` rewrites `/api/(.*)` to the Python function (`api/index.py`); everything else is served by Next.js. Locally, `next dev` alone doesn't run the Python function, so `next.config.ts` proxies `/api/*` to a separately-run `uvicorn` process in that mode (see `docs/04-process.md` and the README) — on Vercel itself, `vercel.json`'s rewrite wins before Next.js ever sees the request.

## Tech stack and why

- **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** — chosen because the goal was to demonstrate a proper frontend, not a notebook. shadcn/ui gives accessible primitives (Card, Badge, Collapsible, Alert) without a heavy component-library dependency.
- **FastAPI, as a Vercel Python serverless function** — Python was the natural choice for the clustering step (scikit-learn), and FastAPI gives typed request/response models (Pydantic) essentially for free, which pays off directly in the Postman/pytest contract tests.
- **Vercel Postgres (Neon)** — a real relational database instead of an in-memory store, so the "ticket count per cluster" and "FAQ per cluster" are actually queryable/joinable data, and the app survives a serverless cold start.
- **scikit-learn (TF-IDF + KMeans)** — deliberately *not* an LLM call for clustering. At 15-20 tickets, TF-IDF + KMeans with a silhouette-score-based choice of k is cheap, deterministic, and testable; an LLM would be non-deterministic and harder to unit test.
- **Gemini (`google-genai`)** — used only where an LLM adds real value: turning a cluster of raw ticket text into a well-phrased question/answer. Free tier keeps the demo cost-free.

## Components and data flow

1. **Upload** (`POST /api/tickets/upload`): the UI posts a CSV; `csv_ingest.py` validates and parses it; the previous ticket/cluster/FAQ batch is cleared and the new tickets are inserted.
2. **Generate** (`POST /api/faqs/generate`): `clustering.py` vectorizes all current tickets with TF-IDF, tries `k` in `[3,5]`, and keeps whichever `k` gets the best silhouette score. For each resulting cluster, `faq_drafting.py` calls Gemini with that cluster's ticket text and top TF-IDF terms, asking for a small JSON object (`theme_title`, `question`, `answer`). Results are persisted as `Cluster` + `FaqEntry` rows, with each `Ticket` updated to point at its assigned cluster.
3. **Fetch** (`GET /api/faqs`): reads the persisted clusters/FAQs back out, so reloading the page doesn't require a new Gemini call.
4. **Frontend**: `TicketUpload` drives step 1; a "Generate FAQs" button drives step 2; `ClusterCard` renders each theme from step 2/3, with ticket IDs behind a collapsible disclosure.

## Security, scalability, usability tradeoffs (prototype-appropriate)

- **No auth**: acceptable because this is a single-user demo; a real deployment would need at least a login wall before exposing an upload endpoint.
- **CORS is wide open (`allow_origins=["*"]`)**: fine for a same-origin Vercel deployment demo; would be tightened to the actual frontend origin in production.
- **Whole-batch replace instead of incremental append**: simpler to reason about and test than merge semantics, at the cost of not supporting "add 5 more tickets to what's already there."
- **Gemini failure is non-fatal**: every drafting call has a template fallback, so a flaky/rate-limited LLM call degrades FAQ quality rather than breaking the endpoint (see `api/_lib/faq_drafting.py`).
- **CSV upload size**: bounded by Vercel's default request body limit, which is generous for a 15-20 row (or even few-thousand row) CSV but would need chunked/streaming ingestion for very large exports.
