# Feature Roadmap: Beyond CSV → FAQs

## Why this exists

The prototype does one thing well: turn a batch of resolved tickets into
recurring themes and a drafted FAQ per theme (see `01-problem-and-scope.md`).
That's **knowledge generation**. It doesn't yet help anyone *find* or
*interrogate* that knowledge once it exists. This doc lays out the next
layer - retrieval and investigation on top of generation - so the app reads
as a small support-knowledge system rather than a one-shot script.

Three pillars, reusing the same pipeline output at each stage:

```
Knowledge generation      Resolved tickets -> themes -> FAQs   (built)
Knowledge retrieval       "which theme/FAQ covers X?"          (this doc)
Knowledge investigation   "what do these tickets actually say?" (this doc)
```

## Constraints this roadmap has to respect

Carried over from `03-architecture.md` and what's actually been built since:

- **Serverless, mostly stateless.** `api/index.py` is a Vercel Python
  function; a request has no memory of a previous one. The one exception
  today is `api/_lib/category_store.py` (Vercel KV), added specifically
  because a human decision - "make this custom category permanent" - needed
  to survive across requests. Any new feature that needs to remember
  something across requests (an "Ask about this theme" conversation, an
  edited FAQ's approval status) needs the same kind of explicit, narrow
  persistence - not a general database brought back "just in case."
- **Gemini is rate-limited on the free tier.** `faq_drafting.py` was
  changed from one Gemini call per cluster to one batched call per generate
  request specifically because 5 separate calls exhausted the free tier's
  request quota. Any new Gemini-backed feature (investigation Q&A,
  resolution comparison) needs to default to on-demand, user-triggered
  calls - never something that fires automatically per cluster on every
  generate.
- **No ticket attachments in the data model today.** `csv_ingest.py` reads
  `subject`/`description`/`resolution` columns only. "Attachment-aware
  investigation" needs a data model change before it needs a UI.
- **Everything must degrade to something grounded, never a hallucination.**
  The existing pattern (`faq_drafting.py`'s template fallback, the explicit
  "don't invent" instructions in its Gemini prompt) is the house style.
  Every feature below keeps that: cite ticket IDs, and say "not enough
  evidence" rather than guess.

## Prioritized feature list

| # | Feature | Value | Effort | Needs Gemini? | Needs persistence? |
|---|---|---|---|---|---|
| 1 | Ask-about-this-theme (grounded Q&A) | High | Medium | Yes, on-demand | No (stateless per question) |
| 2 | Similar/duplicate ticket detection | High | Medium | No (reuses TF-IDF) | No |
| 3 | Global search (themes/FAQs/tickets/keywords) | High | Low | No | No |
| 4 | New-ticket -> related FAQ lookup | High | Medium | No (reuses #2 + #3) | No |
| 5 | Basic trend stats (counts per theme) | Medium | Low | No | No |
| 6 | Export knowledge base (Markdown/CSV) | Medium | Low | No | No |
| 7 | Resolution comparison within a theme | Medium | Medium | Yes, on-demand | No |
| 8 | FAQ review status (draft/approved/needs-review) | Medium | Low | No | Yes (small, KV-backed) |
| 9 | Insufficient-evidence handling | High | Low | N/A (a prompt/UI contract, not a new feature) | No |
| 10 | Attachment-aware investigation | Medium | High | Maybe | Yes (file storage) |

Dropped from consideration (low value-to-effort at this project's scale):
full video/image understanding, an autonomous multi-step agent. Both need
infrastructure (media storage, an agent loop with its own failure modes)
disproportionate to what a resolved-ticket-text corpus actually calls for.

## Feature specs

### 1. Ask-about-this-theme (grounded Q&A)

The centerpiece: pick a theme, ask a free-text question, get an answer
grounded only in that theme's member tickets, with ticket-ID citations.

- **API**: `POST /api/themes/{cluster_id}/ask` - but since clusters aren't
  persisted server-side today, the request body carries the theme's own
  tickets back (the frontend already has them from the last `generate`
  response), e.g. `{ "question": str, "tickets": [...] }`. No new storage;
  the endpoint is a pure function of what it's given, like
  `faq_drafting.py` today.
- **Backend**: new `api/_lib/ticket_qa.py`, same shape as
  `faq_drafting.py` - a prompt built from the question + the theme's
  tickets only, instructed to answer only from that evidence, cite ticket
  IDs, and explicitly say "the tickets don't cover this" when they don't
  (see #9). On any Gemini failure, return a clear "investigation
  unavailable right now" response - there's no safe deterministic template
  for an open-ended question, so the honest fallback is "can't answer,"
  not a guess.
- **Frontend**: a small chat-style panel inside `ClusterCard`'s expanded
  state, reusing the "Show source tickets" disclosure's tickets as context.

### 2. Similar/duplicate ticket detection

Given one new ticket's text, rank the existing batch's tickets by
similarity and surface the closest ones + their theme.

- **Backend**: `api/_lib/clustering.py` already builds a TF-IDF matrix and
  cosine similarity; this is the same machinery run in "query mode" -
  vectorize the new ticket against the existing corpus's fitted vocabulary
  and rank by cosine similarity, no new dependency.
- **API**: `POST /api/tickets/similar` taking `{ "subject", "description",
  "tickets": [...] }` (the existing batch, since nothing's persisted) and
  returning ranked `{ ticket_id, similarity, theme }`.
- No Gemini call needed - this is the same deterministic, explainable
  approach the rest of clustering uses.

### 3. Global search across themes/FAQs/tickets/keywords

A single search box over the *current* generate result (no server round
trip needed - everything it searches is already in the browser from the
last response).

- **Frontend-only.** Filter `GenerateResponse.clusters` client-side by
  substring match against theme, keywords, FAQ question/answer, and
  ticket subjects/IDs. This is the cheapest item on the list and should
  ship early - it makes the existing data meaningfully more usable with no
  backend change at all.

### 4. New-ticket -> related FAQ lookup

Compose #2 (find similar tickets) with the FAQ each match's theme already
has: paste a new ticket's text, get back the relevant FAQ + similar past
tickets in one view. Pure composition, no new backend logic once #2 and #3
(or a small identical lookup) exist.

### 5. Basic trend stats

`GenerateResponse` already has everything needed (`ticket_count` per
cluster, `total_tickets`). A small stats strip - most common theme,
tickets-per-theme bar - is frontend-only, using data already returned.

### 6. Export the knowledge base

`GET`-free: a frontend "Download Markdown" / "Download CSV" button that
serializes the current `GenerateResponse` into a file client-side
(`Blob` + `URL.createObjectURL`), no backend endpoint needed. Markdown
output: one `##` heading per theme, the FAQ, numbered resolution steps,
and a "Source tickets" list - mirrors `ClusterCard`'s own layout.

### 7. Resolution comparison within a theme

"Were these tickets fixed the same way?" - a second on-demand,
user-triggered Gemini prompt (not run automatically per theme, for the
same quota reason batching was introduced) that groups a theme's
resolutions into a small number of resolution *patterns* and names each.
Same module as #1 (`ticket_qa.py`) is a reasonable home; same "no
evidence, say so" contract.

### 8. FAQ review status (draft / approved / needs-review)

The one item here that legitimately needs to remember something between
requests: an approval status per FAQ. Follow the pattern
`category_store.py` already established rather than inventing a second
storage mechanism - a small KV-backed store keyed by a stable hash of the
FAQ's theme + ticket IDs (so it survives a re-generate on the same data),
holding just `{ status, updated_at }`. Explicitly session/soft-state, not
a system of record - consistent with `01-problem-and-scope.md`'s existing
stance that this prototype doesn't do accounts or versioning.

### 9. Insufficient-evidence handling

Not a standalone feature - a contract every Gemini-backed addition above
(#1, #7) must follow, and worth calling out on its own because it's the
difference between a demo that looks smart and one that's trustworthy.
The `faq_drafting.py` prompt already says "if the source tickets do not
contain enough information to make a claim, do not invent it"; #1 and #7's
prompts need the same instruction, plus a validated response shape that
allows an explicit "insufficient evidence" answer rather than forcing the
model to always produce a confident-sounding one.

### 10. Attachment-aware investigation

Out of scope until the data model changes: `csv_ingest.py` has no concept
of an attachment today, and CSV can't carry binary files anyway (it'd need
a second upload mechanism - a zip of files keyed by ticket ID, or links to
already-hosted files). Worth a line in the roadmap so it's not forgotten,
but it's the highest-effort item here for a support/demo project at this
scale and shouldn't block the rest.

## Suggested build order

1. **#3 global search** and **#5 stats** and **#6 export** together first -
   all frontend-only, all reuse data already in `GenerateResponse`, and
   they make the existing output noticeably more useful in an afternoon.
2. **#2 similar-ticket detection**, since it's pure reuse of
   `clustering.py`'s existing TF-IDF machinery and unlocks #4 for free.
3. **#1 ask-about-this-theme**, the highest-value item, once #9's
   evidence-honesty contract is written down as the shared prompt pattern
   for every Gemini Q&A feature that follows.
4. **#4 new-ticket lookup** as a thin composition of #2 + the FAQ already
   attached to that ticket's theme.
5. **#7 resolution comparison** and **#8 FAQ review status** as follow-ups
   once the above are stable - #7 reuses #1's module, #8 reuses the KV
   pattern from `category_store.py`.
6. **#10 attachments** only if there's a real dataset with attachments to
   design against - building it speculatively risks guessing the wrong
   shape.

## Non-goals (unchanged from `01-problem-and-scope.md`)

Authentication/multi-tenant accounts, live helpdesk API ingestion, and
historical run comparison stay out of scope. None of the features above
require revisiting that.
