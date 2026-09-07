from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    business_goal: str = Field(default="", max_length=4000)


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class SiteCreate(BaseModel):
    project_id: str
    url: HttpUrl


class SiteRead(SiteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class AuditCreate(BaseModel):
    project_id: str
    site_id: str
    goal: str = Field(default="", max_length=4000)


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    site_id: str
    goal: str
    status: str
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    audit_id: str
    page_id: str
    category: str
    severity: str
    confidence: float
    title: str
    description: str
    recommendation: str
    status: str


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_id: str
    action_type: str
    rationale: str
    payload: dict
    status: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


class RecommendationDecision(BaseModel):
    reason: str = Field(default="", max_length=2000)


class SearchResult(BaseModel):
    chunk_id: str
    page_id: str
    url: str
    content: str
    score: float
