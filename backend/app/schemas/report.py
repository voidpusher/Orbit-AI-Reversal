from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportListItem(BaseModel):
    id: str
    analysis_id: str
    target_url: str
    product_name: str
    headline: str
    overall_confidence: int
    pages_explored: int
    features_count: int
    is_favorite: bool
    label: str | None
    model_name: str
    published_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    next_cursor: str | None = None


class ReportDetail(ReportListItem):
    summary: str
    evidence_count: int
    document: dict[str, Any]


class UpdateReportRequest(BaseModel):
    is_favorite: bool | None = None
    label: str | None = None


class ExportRequest(BaseModel):
    format: str = "json"  # json | markdown


class ExportResponse(BaseModel):
    format: str
    filename: str
    content: str


class StatsResponse(BaseModel):
    total_analyses: int
    completed_reports: int
    favorites: int
    average_confidence: int


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    organization: str
    plan: str


class CompareSide(BaseModel):
    id: str
    product_name: str
    host: str
    target_url: str
    overall_confidence: int
    pages_explored: int
    evidence_count: int
    features_count: int
    technologies_count: int


class TechDiffItem(BaseModel):
    name: str
    category: str
    confidence: int


class ComparisonResponse(BaseModel):
    a: CompareSide
    b: CompareSide
    similarity: int
    confidence_delta: int
    headline: str
    shared_tech: list[TechDiffItem]
    only_a_tech: list[TechDiffItem]
    only_b_tech: list[TechDiffItem]
    shared_features: list[str]
    only_a_features: list[str]
    only_b_features: list[str]
    shared_insights: list[str]
    architecture_a: list[str]
    architecture_b: list[str]
