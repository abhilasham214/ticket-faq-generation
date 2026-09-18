from typing import List

from pydantic import BaseModel, ConfigDict


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    subject: str


class UploadResponse(BaseModel):
    ticket_count: int
    preview: List[TicketOut]


class FaqOut(BaseModel):
    question: str
    answer: str


class ClusterOut(BaseModel):
    cluster_id: int
    theme_title: str
    ticket_count: int
    ticket_ids: List[str]
    top_terms: List[str]
    faq: FaqOut


class GenerateResponse(BaseModel):
    clusters: List[ClusterOut]
    total_tickets: int


class HealthResponse(BaseModel):
    status: str
    db: str


class ErrorResponse(BaseModel):
    detail: str
