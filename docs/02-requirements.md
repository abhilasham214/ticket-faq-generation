# Requirements

## User stories

**US-1 — Upload resolved tickets**
As a support lead, I can upload a CSV of resolved tickets so the system has data to find recurring themes in.

**US-2 — See recurring themes**
As a support lead, I can see my tickets grouped into a small number of recurring issue themes, with a count of how many tickets belong to each, so I know where the repeated pain points are.

**US-3 — Get a draft FAQ per theme**
As a support lead, I can get a drafted FAQ entry (question + answer) for each theme so I have a starting point to publish to the knowledge base instead of writing one from scratch.

**US-4 — Trust the FAQ is grounded**
As a support lead, I can see which source tickets a theme's FAQ came from, so I can verify the draft is grounded in real resolutions before publishing it.

**US-5 — Come back later without recomputing**
As a support lead, I can reload the page and still see the last generated themes and FAQs, so I don't lose the result of a run I already paid for (in Gemini calls and my own time).

## Acceptance criteria

| Story | Acceptance criteria |
|---|---|
| US-1 | Given a CSV with `subject`, `description`, `resolution` columns and 15-20 rows, when I upload it, then I see a confirmation with the correct row count. Given a CSV missing a required column, when I upload it, then I see a clear error naming the missing column and nothing is stored. |
| US-2 | Given an uploaded batch of tickets, when I click "Generate FAQs", then I see 3-5 theme cards, each showing a ticket count, and the counts sum to the total uploaded. |
| US-3 | Given a generated theme, then its card shows one question and one answer, both non-empty, and the answer text is drawn from language present in that theme's ticket resolutions (not generic boilerplate). |
| US-4 | Given a theme card, when I expand "Show source tickets", then I see the ticket IDs that were grouped into that theme. |
| US-5 | Given I generated FAQs and then reload the page, then the same themes, counts, and FAQ text reappear without me clicking "Generate" again. |

## Prioritization for the timebox

Must-have (built): CSV upload, algorithmic clustering into recurring themes with deterministic rule-based naming, one Gemini-drafted FAQ per theme (with resolution steps and escalation guidance) and a template fallback, ticket counts and full source-ticket traceability per theme, a Postman-covered API, unit + integration tests.

Should-have, cut for time: in-UI FAQ editing before "publishing," a way to re-run clustering on an incrementally larger ticket set instead of replacing the whole batch, richer clustering diagnostics (e.g. showing per-ticket similarity scores in the UI, not just the API response).

Could-have, deliberately out of scope: authentication/multi-tenant accounts, direct helpdesk API ingestion (Zendesk/Jira/etc.) instead of CSV, historical run comparison.

The must-haves map directly to the assignment's expected output (3-5 clustered themes, one FAQ per cluster, a ticket count per cluster) plus enough surrounding product (upload, persistence, tests) to make it a demoable, not just a script.
