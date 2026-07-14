from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class AnalysisOptions(BaseModel):
    deep_crawl: bool = False
    max_pages: int = Field(default=20, ge=1, le=100)
    capture_network_requests: bool = True
    evidence_mode: Literal["crawl", "har"] = "crawl"


class CreateAnalysisRequest(BaseModel):
    target_url: HttpUrl
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)
    authorized_public_analysis: Literal[True] = True


class HarEntryRequest(BaseModel):
    url: HttpUrl
    method: str = Field(default="GET", min_length=1, max_length=12)
    status: int = Field(default=0, ge=0, le=599)
    resource_type: str | None = Field(default=None, max_length=40)
    content_type: str | None = Field(default=None, max_length=160)
    cache_control: str | None = Field(default=None, max_length=160)
    server: str | None = Field(default=None, max_length=100)


class ImportHarRequest(BaseModel):
    target_url: HttpUrl
    entries: list[HarEntryRequest] = Field(min_length=1, max_length=500)
    authorized_public_analysis: Literal[True] = True


class AnalysisResponse(BaseModel):
    id: str
    target_url: str
    status: str
    progress: int
    options: AnalysisOptions
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    event_stream_url: str
    report_id: str | None = None
    error_code: str | None = None


class AnalysisEventResponse(BaseModel):
    sequence: int
    kind: str
    message: str
    payload: dict[str, Any]
    occurred_at: datetime
