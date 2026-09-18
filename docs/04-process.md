# Process

## From idea to implementation

The build went through a deliberate scoping conversation before any code was written:

1. Started from the bare assignment (cluster resolved tickets into 3-5 themes, draft an FAQ per theme, show ticket counts).
2. Considered a minimal single-script version first, then intentionally scoped up to a full-stack app (Next.js + FastAPI + Postgres + real deployment) to demonstrate REST API design, SQL, data processing, LLM integration, and a real frontend/backend split rather than a notebook.
3. Locked in concrete technology decisions up front (Next.js/Tailwind/shadcn, FastAPI-on-Vercel-Python, Vercel Postgres/Neon, scikit-learn for clustering, Gemini for drafting) so implementation could proceed without re-litigating architecture mid-build.
4. Added a documentation and testing deliverable (this `docs/` folder, the pytest suites, the Postman collection) as an explicit final phase, once the app worked - so these describe what was actually shipped rather than a plan that might have drifted.

## Task breakdown

Work proceeded in this order, each step verified before moving to the next:

1. Scaffold the Next.js app and shadcn/ui components.
2. Build the Python backend: SQLAlchemy models → CSV ingestion → clustering → FAQ drafting → FastAPI routes wiring it together.
3. Build the frontend: API client (`lib/api.ts`) → upload component → cluster card component → page composition.
4. Write and run unit tests (clustering, CSV ingestion, FAQ drafting) against the backend modules in isolation.
5. Write and run integration tests (FastAPI `TestClient` + a throwaway SQLite database per test) covering the full upload → generate → fetch flow, plus negative/edge paths.
6. Smoke-test the real pipeline by hand: ran the FastAPI app with `uvicorn`, uploaded the sample CSV with `curl`, generated FAQs, and confirmed cluster counts and grounded answers; separately confirmed the Next.js dev server proxies `/api/*` to that backend and renders.
7. Built the Postman collection and ran it with Newman against the live local backend until every assertion passed (this caught a real request-ordering bug - see `docs/05-testing.md`).
8. Wrote this documentation set from the finished, verified system.

## Coding conventions followed

- **TypeScript**: strict mode (from `create-next-app` defaults), typed API responses in `lib/api.ts` shared between components rather than `any`.
- **Python**: Pydantic models (`api/_lib/schemas.py`) define the API's request/response contract explicitly rather than returning raw dicts; SQLAlchemy models are kept separate from Pydantic schemas.
- **One responsibility per module**: `csv_ingest.py` only parses/validates CSV, `clustering.py` only clusters, `faq_drafting.py` only talks to Gemini (with the network client injectable for tests) - `api/index.py` only orchestrates.
- **Underscore-prefixed `api/_lib/`**: not just a style choice - Vercel's file-based Python function routing ignores underscore-prefixed paths, which is what keeps `_lib` from being deployed as its own set of (broken) serverless functions.

## How AI-assisted output was validated, not just accepted

An AI coding assistant was used throughout implementation, but nothing it produced was taken on faith:

- **Clustering correctness**: the assistant's first draft of the clustering logic was checked by actually running it against the 20-ticket sample data and inspecting the resulting cluster sizes/labels, not just reading the code - this caught that KMeans on very small ticket counts could return fewer than the minimum viable clusters, which the code now handles explicitly (see `api/_lib/clustering.py`'s single-cluster fallback).
- **FAQ groundedness**: generated FAQ answers were spot-checked against the source tickets' actual `resolution` text (e.g. the "login" theme's answer should reference session/SSO/password concepts that genuinely appear in those tickets) rather than trusting that "it's an LLM call" made it correct.
- **Framework version drift**: the assistant did not assume its training-data knowledge of Next.js applied unchanged - the scaffolded project's generated `AGENTS.md` explicitly flagged that Next.js 16 has breaking changes, so the bundled `node_modules/next/dist/docs/01-app/02-guides/upgrading/version-16.md` was read before writing any App Router code, which is how the `LayoutProps` type-helper requirement (see `docs/05-testing.md`) was anticipated rather than guessed at.
- **Postman collection**: not just written and left - it was actually executed against a running backend with Newman, which surfaced a real ordering bug (detailed in `docs/05-testing.md`) that a read-through would not have caught.
- **Generated boilerplate reviewed by hand**: the SQLAlchemy schema, the FastAPI route bodies, and the multipart request bodies in the Postman collection were all read and reasoned about line-by-line (e.g. checking that `upload_tickets` clears `FaqEntry`/`Cluster`/`Ticket` in FK-safe order) rather than accepted as opaque generated code.
