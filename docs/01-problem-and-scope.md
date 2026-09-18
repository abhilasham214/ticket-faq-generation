# Problem & Scope

## Problem, in plain words

Support teams resolve the same handful of underlying problems over and over — a password reset that silently fails, a billing discrepancy, a flaky webhook — but each resolution lives in its own closed ticket. Nobody aggregates them into something a teammate can search before opening a new ticket. This project builds a small tool that takes a batch of already-resolved tickets, groups them into a handful of recurring themes, and drafts a ready-to-publish FAQ entry for each theme.

## Business objective

Reduce repeated support effort by turning ticket history into a lightweight, always-current knowledge base draft: fewer duplicate tickets, faster time-to-resolution for recurring issues, and a starting point a human editor can polish rather than write from scratch.

## Assumptions

- Ticket volume is small (15-20 for the demo dataset; the clustering approach is chosen to work well at that scale, not necessarily at 10,000+ tickets).
- Tickets are already resolved and each has a subject, description, and resolution — no live/open-ticket handling.
- A single user/team owns the data at a time (no multi-tenant separation).
- "Good enough to publish after a quick human read" is the bar for FAQ quality, not "publish unreviewed."

## Constraints

- Built for a fixed, short timebox (a hackathon-style build), so scope is deliberately narrow.
- FAQ drafting depends on the Gemini free tier, which has request-rate limits — the drafting step includes a template fallback specifically so the app still works if a call fails or no key is configured.
- Hosting is entirely on Vercel (frontend, Python API, and Postgres), which shapes the backend as serverless functions rather than a long-running server.

## In scope for this prototype

- Upload a CSV of resolved tickets through the UI.
- Cluster tickets into 3-5 recurring themes algorithmically (TF-IDF + KMeans).
- Draft one FAQ entry (question + answer) per theme via Gemini, grounded in that theme's actual ticket resolutions.
- Show ticket counts per theme and which tickets belong to each.
- Persist the latest batch and its FAQs so a page reload doesn't lose them.

## Out of scope for this prototype

- Authentication / multi-user accounts.
- Editing or approving FAQ text in the UI before publishing elsewhere.
- Incremental re-clustering as new tickets trickle in (each generate run replaces the previous batch wholesale).
- Versioning/history of past clustering runs.
- Ingesting tickets from a live helpdesk API (CSV upload only).
