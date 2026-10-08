from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class AskReportRequest(BaseModel):
    question: str


class CopilotCitation(BaseModel):
    id: str
    section: str
    title: str
    evidence: str
    classification: str
    confidence: int


class AskReportResponse(BaseModel):
    answer: str
    basis: str
    confidence: int
    citations: list[CopilotCitation]
    limitations: list[str]
    followups: list[str]


class CompileWorkflowRequest(BaseModel):
    flow_name: str


class WorkflowSummary(BaseModel):
    name: str
    steps: int
    confidence: int
    classification: str


class WorkflowListResponse(BaseModel):
    items: list[WorkflowSummary]


class CompileWorkflowResponse(BaseModel):
    contract: dict[str, Any]
    playwright: str
    contract_json: str


class SaveWorkflowRequest(BaseModel):
    contract: dict[str, Any]
    schedule: str = "manual"


class RunWorkflowRequest(BaseModel):
    inputs: dict[str, str] = Field(default_factory=dict)


class WorkflowDefinitionResponse(BaseModel):
    id: str
    report_id: str
    name: str
    target_url: str
    version: int
    status: str
    schedule: str
    contract: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    next_run_at: datetime | None


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    failure_step_id: str | None
    error_code: str | None
    result: dict[str, Any]
    repair_proposal: dict[str, Any] | None


class SavedWorkflowListResponse(BaseModel):
    items: list[WorkflowDefinitionResponse]


class WorkflowRunListResponse(BaseModel):
    items: list[WorkflowRunResponse]


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
