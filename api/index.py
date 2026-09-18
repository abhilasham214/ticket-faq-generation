from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ._lib.clustering import ClusteringError, cluster_tickets
from ._lib.csv_ingest import CsvValidationError, parse_tickets_csv
from ._lib.faq_drafting import draft_faq_for_cluster
from ._lib.schemas import ClusterOut, FaqOut, GenerateResponse, HealthResponse

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

    try:
        clusters = cluster_tickets(tickets)
    except ClusteringError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result: List[ClusterOut] = []
    for i, cluster in enumerate(clusters):
        member_tickets = [tickets[idx] for idx in cluster["ticket_indices"]]
        faq = draft_faq_for_cluster(cluster, member_tickets)
        result.append(
            ClusterOut(
                cluster_id=i + 1,
                theme_title=faq["theme_title"],
                ticket_count=cluster["ticket_count"],
                ticket_ids=cluster["ticket_ids"],
                top_terms=cluster["top_terms"],
                faq=FaqOut(question=faq["question"], answer=faq["answer"]),
            )
        )

    return GenerateResponse(clusters=result, total_tickets=len(tickets))
