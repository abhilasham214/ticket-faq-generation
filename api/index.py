from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as sql_text

from ._lib import models
from ._lib.clustering import ClusteringError, cluster_tickets
from ._lib.csv_ingest import CsvValidationError, parse_tickets_csv
from ._lib.db import SessionLocal, engine, init_db
from ._lib.faq_drafting import draft_faq_for_cluster
from ._lib.schemas import (
    ClusterOut,
    FaqOut,
    GenerateResponse,
    HealthResponse,
    TicketOut,
    UploadResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Ticket FAQ Auto Builder API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        return HealthResponse(status="ok", db="connected")
    except Exception as exc:  # pragma: no cover - depends on live DB availability
        return HealthResponse(status="degraded", db=str(exc))


@app.post("/api/tickets/upload", response_model=UploadResponse)
async def upload_tickets(file: UploadFile = File(...)) -> UploadResponse:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = await file.read()
    try:
        rows = parse_tickets_csv(content)
    except CsvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db = SessionLocal()
    try:
        db.query(models.FaqEntry).delete()
        db.query(models.Cluster).delete()
        db.query(models.Ticket).delete()

        ticket_rows = [models.Ticket(**row) for row in rows]
        db.add_all(ticket_rows)
        db.commit()

        for row in ticket_rows:
            db.refresh(row)

        preview = [TicketOut.model_validate(row) for row in ticket_rows[:5]]
        return UploadResponse(ticket_count=len(ticket_rows), preview=preview)
    finally:
        db.close()


@app.post("/api/faqs/generate", response_model=GenerateResponse)
def generate_faqs() -> GenerateResponse:
    db = SessionLocal()
    try:
        tickets = db.query(models.Ticket).all()
        if not tickets:
            raise HTTPException(status_code=400, detail="No tickets uploaded yet.")

        ticket_dicts = [
            {
                "id": t.id,
                "external_id": t.external_id,
                "subject": t.subject,
                "description": t.description,
                "resolution": t.resolution,
            }
            for t in tickets
        ]

        try:
            clusters = cluster_tickets(ticket_dicts)
        except ClusteringError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        db.query(models.FaqEntry).delete()
        db.query(models.Cluster).delete()
        db.commit()

        result: List[ClusterOut] = []
        for cluster in clusters:
            member_tickets = [ticket_dicts[i] for i in cluster["ticket_indices"]]
            faq = draft_faq_for_cluster(cluster, member_tickets)

            cluster_row = models.Cluster(
                theme_title=faq["theme_title"],
                top_terms=cluster["top_terms"],
                ticket_count=cluster["ticket_count"],
            )
            db.add(cluster_row)
            db.flush()

            member_ids = [t["id"] for t in member_tickets]
            db.query(models.Ticket).filter(models.Ticket.id.in_(member_ids)).update(
                {"cluster_id": cluster_row.id}, synchronize_session=False
            )

            faq_row = models.FaqEntry(
                cluster_id=cluster_row.id,
                question=faq["question"],
                answer=faq["answer"],
            )
            db.add(faq_row)

            result.append(
                ClusterOut(
                    cluster_id=cluster_row.id,
                    theme_title=faq["theme_title"],
                    ticket_count=cluster["ticket_count"],
                    ticket_ids=cluster["ticket_ids"],
                    top_terms=cluster["top_terms"],
                    faq=FaqOut(question=faq["question"], answer=faq["answer"]),
                )
            )

        db.commit()
        return GenerateResponse(clusters=result, total_tickets=len(tickets))
    finally:
        db.close()


@app.get("/api/faqs", response_model=GenerateResponse)
def get_faqs() -> GenerateResponse:
    db = SessionLocal()
    try:
        clusters = db.query(models.Cluster).order_by(models.Cluster.id).all()
        total = db.query(models.Ticket).count()

        result: List[ClusterOut] = []
        for cluster in clusters:
            if cluster.faq is None:
                continue
            result.append(
                ClusterOut(
                    cluster_id=cluster.id,
                    theme_title=cluster.theme_title,
                    ticket_count=cluster.ticket_count,
                    ticket_ids=[t.external_id for t in cluster.tickets],
                    top_terms=cluster.top_terms or [],
                    faq=FaqOut(question=cluster.faq.question, answer=cluster.faq.answer),
                )
            )
        return GenerateResponse(clusters=result, total_tickets=total)
    finally:
        db.close()
