from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ._lib.category_discovery import discover_category
from ._lib.category_store import CategoryStoreError, add_custom_category, list_custom_categories
from ._lib.cluster_naming import has_curated_match, name_cluster
from ._lib.clustering import ClusteringError, cluster_tickets
from ._lib.csv_ingest import CsvValidationError, parse_tickets_csv
from ._lib.domain_categories import merged_categories
from ._lib.faq_drafting import draft_faqs_for_clusters
from ._lib.schemas import (
    CategoryIn,
    CategoryOut,
    ClusterOut,
    FaqOut,
    GenerateResponse,
    HealthResponse,
    TicketSummary,
)

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


@app.post("/api/faqs/generate", response_model=GenerateResponse)
async def generate_faqs(file: UploadFile = File(...)) -> GenerateResponse:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = await file.read()
    try:
        tickets = parse_tickets_csv(content)
    except CsvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    return GenerateResponse(clusters=result, total_tickets=len(tickets))


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
