from typing import Any, Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ._lib.category_discovery import discover_category
from ._lib.category_store import CategoryStoreError, add_custom_category, list_custom_categories
from ._lib.cluster_naming import has_curated_match, name_cluster
from ._lib.clustering import ClusteringError, cluster_tickets
from ._lib.csv_ingest import CsvValidationError, parse_tickets_csv
from ._lib.domain_categories import merged_categories
from ._lib.faq_drafting import draft_faqs_for_clusters
from ._lib.result_store import get_latest_result, save_latest_result
from ._lib.schemas import (
    CategoryIn,
    CategoryOut,
    ClusterOut,
    FaqOut,
    GenerateResponse,
    HealthResponse,
    TicketAskIn,
    TicketAskOut,
    TicketSummary,
)
from ._lib.ticket_qa import ask_about_ticket
from ._lib.ticket_store import get_seeded_tickets

app = FastAPI(title="Ticket FAQ Auto Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _generate_response_for_tickets(tickets: List[Dict[str, Any]]) -> GenerateResponse:
    """The full parse-to-FAQs pipeline, shared by every endpoint that produces
    a GenerateResponse - the only difference between them is where `tickets`
    comes from. Every call's result is saved as "the latest result" (best
    effort - see result_store.py), so GET /api/faqs/latest can hand it back
    on the next visit instead of the app opening empty.
    """
    # User-approved custom categories (see POST /api/categories) get the same
    # tag-bridging boost and curated naming as the 5 built-in domains, so a
    # theme only needs Gemini's help the first time it shows up.
    categories = merged_categories(list_custom_categories())

    try:
        clusters = cluster_tickets(tickets, categories=categories)
    except ClusteringError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entries = []
    for cluster in clusters:
        member_tickets = [tickets[idx] for idx in cluster["ticket_indices"]]
        theme = name_cluster(cluster["keywords"], categories=categories)
        ai_named = False
        discovered_keywords: List[str] = []

        # A cluster that doesn't match any curated domain is a genuinely new
        # recurring theme rather than one of the 5 taxonomy categories - ask
        # Gemini to name it instead of showing the generic "Recurring Issue:
        # <term>" fallback. Any failure (no key, network error, malformed
        # response) leaves `theme` as the deterministic fallback untouched.
        if not has_curated_match(cluster["keywords"], categories=categories):
            discovered = discover_category(cluster["keywords"], member_tickets)
            if discovered:
                theme = discovered["label"]
                ai_named = True
                discovered_keywords = discovered["keywords"]

        entries.append(
            {
                "theme": theme,
                "ai_named": ai_named,
                "discovered_keywords": discovered_keywords,
                "cluster": cluster,
                "tickets": member_tickets,
            }
        )

    # One Gemini call drafts every cluster's FAQ at once, instead of one call
    # per cluster - keeps a single generate request to a single request
    # against the (often rate-limited) Gemini API regardless of cluster count.
    faqs = draft_faqs_for_clusters(entries)

    result: List[ClusterOut] = []
    for i, (entry, faq) in enumerate(zip(entries, faqs)):
        cluster = entry["cluster"]
        result.append(
            ClusterOut(
                cluster_id=i + 1,
                theme=entry["theme"],
                ai_named=entry["ai_named"],
                discovered_keywords=entry["discovered_keywords"],
                ticket_count=cluster["ticket_count"],
                keywords=cluster["keywords"],
                ticket_ids=cluster["ticket_ids"],
                tickets=[
                    TicketSummary(
                        ticket_id=t["external_id"],
                        title=t["subject"],
                        description=t.get("description", ""),
                        resolution=t["resolution"],
                    )
                    for t in entry["tickets"]
                ],
                faq=FaqOut(
                    question=faq["question"],
                    answer=faq["answer"],
                    resolution_steps=faq["resolution_steps"],
                    escalation=faq["escalation"],
                ),
            )
        )

    response = GenerateResponse(clusters=result, total_tickets=len(tickets))
    save_latest_result(response.model_dump())
    return response


@app.get("/api/faqs/latest", response_model=GenerateResponse)
def get_latest_faqs() -> GenerateResponse:
    """What the homepage loads by default: the last generated result if one
    exists (from an uploaded CSV or the sample button, from any visitor -
    there's no per-user session, see result_store.py), otherwise the seeded
    sample set generated fresh, so the app never opens empty.
    """
    stored = get_latest_result()
    if stored is not None:
        return GenerateResponse(**stored)

    tickets = get_seeded_tickets()
    if not tickets:
        raise HTTPException(status_code=503, detail="No data is available yet.")
    return _generate_response_for_tickets(tickets)


@app.post("/api/faqs/generate", response_model=GenerateResponse)
async def generate_faqs(file: UploadFile = File(...)) -> GenerateResponse:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = await file.read()
    try:
        tickets = parse_tickets_csv(content)
    except CsvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _generate_response_for_tickets(tickets)


@app.post("/api/faqs/generate/sample", response_model=GenerateResponse)
def generate_faqs_from_sample() -> GenerateResponse:
    """Run the exact same pipeline as POST /api/faqs/generate, but sourced
    from a small seeded demo ticket set instead of an uploaded CSV, so the
    app has something to show on first load without requiring a file first.
    The seed set is persisted in Vercel KV (ticket_store.py) after its first
    read, falling back to the bundled data/sample_tickets.csv either way.
    """
    tickets = get_seeded_tickets()
    if not tickets:
        raise HTTPException(status_code=503, detail="No sample tickets are available right now.")

    return _generate_response_for_tickets(tickets)


@app.post("/api/categories", response_model=CategoryOut, status_code=201)
def add_category(payload: CategoryIn) -> CategoryOut:
    """Promote a Gemini-discovered theme (see the frontend's "Add as new
    domain" popup) into a permanent custom category, persisted in Vercel KV
    so it applies to every future /api/faqs/generate call, not just this
    session. Requires KV_REST_API_URL/KV_REST_API_TOKEN to be configured;
    without them this 503s rather than silently pretending the choice was
    saved.
    """
    if not payload.label.strip():
        raise HTTPException(status_code=400, detail="label must not be empty.")

    try:
        entry = add_custom_category(payload.label, payload.keywords)
    except CategoryStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return CategoryOut(**entry)


@app.post("/api/tickets/ask", response_model=TicketAskOut)
def ask_about_ticket_endpoint(payload: TicketAskIn) -> TicketAskOut:
    """"Discuss" a single source ticket - a free-text question answered from
    only that ticket's own subject/description/resolution (the caller sends
    the ticket's own fields back, same as everywhere else in this stateless
    app - nothing is looked up server-side). 503s if Gemini isn't configured
    or the call fails - there's no safe deterministic fallback for an
    open-ended question, so this doesn't pretend to answer.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty.")

    ticket = {
        "title": payload.title,
        "description": payload.description,
        "resolution": payload.resolution,
    }
    result = ask_about_ticket(ticket, payload.question)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Investigation isn't available right now. Make sure GEMINI_API_KEY is set, or try again in a moment.",
        )

    return TicketAskOut(answer=result["answer"])
