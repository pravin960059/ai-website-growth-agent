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


class ConnectorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    provider: str
    external_account_id: str | None
    config: dict
    status: str
    created_by: str
    created_at: datetime


class OAuthStartRead(BaseModel):
    provider: str
    authorization_url: str
    expires_at: datetime


class AutonomyPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    enabled: bool
    autonomy_level: int
    allowed_action_types: list[str]
    allowed_paths: list[str]
    max_files_per_pr: int
    max_diff_bytes: int
    max_open_prs: int
    require_human_approval: bool
    updated_by: str
    updated_at: datetime


class AutonomyPolicyUpdate(BaseModel):
    enabled: bool | None = None
    autonomy_level: int | None = Field(default=None, ge=0, le=2)
    allowed_action_types: list[str] | None = None
    allowed_paths: list[str] | None = None
    max_files_per_pr: int | None = Field(default=None, ge=1, le=100)
    max_diff_bytes: int | None = Field(default=None, ge=1_000, le=1_000_000)
    max_open_prs: int | None = Field(default=None, ge=1, le=20)
    require_human_approval: bool | None = None


class SearchObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    connector_id: str
    property_url: str
    query: str
    page_url: str
    country: str
    device: str
    clicks: float
    impressions: float
    ctr: float
    position: float
    start_date: str
    end_date: str
    observed_at: datetime


class SearchConsoleSyncRead(BaseModel):
    provider: str
    property_url: str
    start_date: str
    end_date: str
    rows_imported: int


class GrowthRunCreate(BaseModel):
    site_id: str
    trigger: str = Field(default="manual", pattern="^(manual|scheduled|search_signal)$")


class GrowthRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    site_id: str
    trigger: str
    status: str
    audit_id: str | None
    error: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class GitHubFileChange(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=500_000)


class GitHubProposalCreate(BaseModel):
    connector_id: str
    repository: str = Field(pattern=r"^[^/]+/[^/]+$")
    base_branch: str = Field(default="main", min_length=1, max_length=200)
    branch_name: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._/-]+$")
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=20_000)
    changes: list[GitHubFileChange] = Field(min_length=1, max_length=100)


class ActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    recommendation_id: str | None
    action_type: str
    status: str
    idempotency_key: str
    policy_decision: dict
    request: dict
    result: dict
    created_by: str
    created_at: datetime
    completed_at: datetime | None
