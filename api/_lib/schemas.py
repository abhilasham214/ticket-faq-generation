from typing import List

from pydantic import BaseModel, Field


class FaqOut(BaseModel):
    question: str
    answer: str
    resolution_steps: List[str]
    escalation: str


class TicketSummary(BaseModel):
    ticket_id: str
    title: str
    resolution: str


class ClusterOut(BaseModel):
    cluster_id: int
    theme: str
    ai_named: bool
    discovered_keywords: List[str] = Field(default_factory=list)
    ticket_count: int
    keywords: List[str]
    ticket_ids: List[str]
    tickets: List[TicketSummary]
    faq: FaqOut


class GenerateResponse(BaseModel):
    clusters: List[ClusterOut]
    total_tickets: int


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str


class CategoryIn(BaseModel):
    label: str
    keywords: List[str] = Field(default_factory=list)


class CategoryOut(BaseModel):
    id: str
    label: str
    keywords: List[str]
