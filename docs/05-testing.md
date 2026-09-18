# Testing

## Strategy

Four layers, each a real runnable artifact rather than just a written plan:

1. **Unit tests** (`tests/unit/`, `pytest`) — isolate `api/_lib` modules with everything external mocked. Gemini is never called; a `MagicMock` client stands in for it.
2. **Integration tests** (`tests/integration/`, `pytest` + FastAPI `TestClient`) — exercise the real FastAPI app against a throwaway SQLite database per test, through the actual HTTP-shaped request/response cycle, still without calling the real Gemini API (no `GEMINI_API_KEY` set, so drafting deterministically falls back to the template).
3. **Live API smoke tests** (`tests/api/test_live_api.py`) — black-box `httpx` calls against a *running* instance (`BASE_URL` env var), skipped unless that variable is set. A couple of CI-friendly checks for environments without Newman.
4. **Postman collection** (`postman/ticket-faq-api.postman_collection.json`) — the primary black-box contract suite: one folder per concern, every request carrying `pm.test(...)` assertions, runnable via the Postman GUI or `newman`.

Run everything backend-side with:

```bash
pytest                    # unit + integration (tests/api is skipped without BASE_URL)
```

Run the Postman suite against a running backend with:

```bash
newman run postman/ticket-faq-api.postman_collection.json \
  -e postman/ticket-faq-api.postman_environment.json \
  --env-var baseUrl=http://localhost:8000 \
  --working-dir .
```

## Test matrix by endpoint

| Endpoint | Functional | Negative | Edge |
|---|---|---|---|
| `GET /api/health` | Returns `200` with `status`/`db` fields | — | — |
| `POST /api/tickets/upload` | Valid CSV → `200`, correct `ticket_count`, preview capped at 5 | Non-CSV file → `400`; missing required column → `400` naming the column | Extra unrecognized column ignored, still `200`; duplicate identical rows both counted; re-upload replaces the previous batch (clusters/FAQs cleared) |
| `POST /api/faqs/generate` | `200`, cluster count in `[3,5]`, counts sum to total, every FAQ has non-empty question/answer | Zero tickets uploaded → handled `4xx`, never `500` | Very small ticket count (2) still returns a result instead of crashing (falls back to a single cluster below the `[3,5]` range) |
| `GET /api/faqs` | Returns the same clusters/FAQs a prior `generate` call produced, for reload without recompute | — | Called before any `generate` → empty `clusters` list, not an error |

Covered concretely in: `tests/unit/test_clustering.py`, `tests/unit/test_csv_ingest.py`, `tests/unit/test_faq_drafting.py`, `tests/integration/test_api_flow.py`, and the Postman collection's four folders.

## Defects found & fixed during implementation

These are real issues hit while building this project, not hypothetical:

1. **`create-next-app` rejected the target directory name.** npm package names can't contain capital letters, and the project directory (`Ticket_FAQ_generation`) does. *Fix*: scaffolded into a temp directory with a valid name, then copied the generated files in and renamed `package.json`'s `name` field.
2. **Copying `node_modules` was extremely slow on Windows via a POSIX `cp -r`.** *Fix*: copied only the source files, then ran a native `npm install` in place, which was orders of magnitude faster.
3. **`greenlet` (a transitive SQLAlchemy dependency) failed to build from source.** pip resolved a `greenlet` version with no prebuilt wheel for the local Python 3.9, and no C++ build tools were available. *Fix*: pinned `greenlet==3.2.4` in `requirements.txt`, a version that does ship a matching wheel.
4. **TypeScript build failed with `Cannot find name 'LayoutProps'`.** Next.js 16 generates global `PageProps`/`LayoutProps` type helpers via `next dev`/`next build`/`next typegen`, which hadn't been run yet. *Fix*: ran `npx next typegen` once; documented that a fresh checkout needs one dev/build/typegen pass before `tsc --noEmit` is meaningful.
5. **Integration test teardown failed with `PermissionError` deleting the SQLite temp file.** The SQLAlchemy engine still held an open connection to it. *Fix*: call `engine.dispose()` before removing the file.
6. **Integration tests leaked state into each other via a cached database engine.** `api/_lib/db.py` resolves its connection string from the environment at *import* time, so changing `TEST_DATABASE_URL` between tests had no effect once the module was cached. *Fix*: the `client` fixture clears `api.*` from `sys.modules` before and after each test so a fresh engine binds to that test's own database file.
7. **Postman collection had a request-ordering bug.** The negative/edge-case upload requests originally ran *between* the valid 20-row upload and the "Generate FAQs" request, so by the time "Generate" ran, the ticket table held the 2-row duplicate-edge-case batch instead - the "3 to 5 clusters" assertion failed with `1`, which is correct clustering behavior for 2 tickets but the wrong data to be testing against. Only caught by actually running the collection with Newman, not by reading the JSON. *Fix*: reordered the collection so the functional chain (valid upload → generate → get) runs uninterrupted, with negative/edge upload cases moved to a folder that runs afterward.
8. **Postman file-upload requests aren't portable via a committed `src` path alone.** Referencing a local file path works for the one happy-path CSV upload (documented as needing re-selection in the Postman GUI, a normal Postman limitation), but isn't practical for several small variant CSVs. *Fix*: those negative/edge requests use an inline raw `multipart/form-data` body with a literal boundary and CRLF line endings, so they're fully self-contained in the collection JSON with no external file dependency.
