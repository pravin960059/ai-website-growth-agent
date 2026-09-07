from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_actor
from .db import get_db, init_db
from .models import Audit, AuditEvent, Finding, Project, Recommendation, Site
from .retrieval import search_chunks
from .schemas import (
    AuditCreate,
    AuditRead,
    FindingRead,
    ProjectCreate,
    ProjectRead,
    RecommendationDecision,
    RecommendationRead,
    SearchResult,
    SiteCreate,
    SiteRead,
)
from .settings import get_settings
from .workflow import run_audit_sync


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_base_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ready"}


@app.post("/api/v1/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), _: str = Depends(get_actor)) -> Project:
    project = Project(name=payload.name, business_goal=payload.business_goal)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/v1/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db), _: str = Depends(get_actor)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())).all())


@app.post("/api/v1/sites", response_model=SiteRead)
def create_site(payload: SiteCreate, db: Session = Depends(get_db), _: str = Depends(get_actor)) -> Site:
    if not db.get(Project, payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    site = Site(project_id=payload.project_id, url=str(payload.url).rstrip("/"))
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@app.post("/api/v1/audits", response_model=AuditRead)
def create_audit(payload: AuditCreate, db: Session = Depends(get_db), _: str = Depends(get_actor)) -> Audit:
    site = db.get(Site, payload.site_id)
    if not site or site.project_id != payload.project_id:
        raise HTTPException(status_code=404, detail="Site not found for project")
    audit = Audit(project_id=payload.project_id, site_id=payload.site_id, goal=payload.goal)
    db.add(audit)
    db.flush()
    db.add(AuditEvent(audit_id=audit.id, event_type="audit.created"))
    db.commit()
    db.refresh(audit)
    return audit


@app.post("/api/v1/audits/{audit_id}/run", response_model=AuditRead)
def run_audit(audit_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), _: str = Depends(get_actor)) -> Audit:
    audit = db.get(Audit, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status not in {"queued", "failed"}:
        raise HTTPException(status_code=409, detail=f"Audit is already {audit.status}")
    audit.status = "queued"
    audit.error = None
    db.commit()
    background_tasks.add_task(run_audit_sync, audit.id)
    db.refresh(audit)
    return audit


@app.get("/api/v1/audits/{audit_id}", response_model=AuditRead)
def get_audit(audit_id: str, db: Session = Depends(get_db), _: str = Depends(get_actor)) -> Audit:
    audit = db.get(Audit, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return audit


@app.get("/api/v1/audits/{audit_id}/findings", response_model=list[FindingRead])
def list_findings(audit_id: str, db: Session = Depends(get_db), _: str = Depends(get_actor)) -> list[Finding]:
    if not db.get(Audit, audit_id):
        raise HTTPException(status_code=404, detail="Audit not found")
    return list(db.scalars(select(Finding).where(Finding.audit_id == audit_id).order_by(Finding.severity.desc())).all())


@app.get("/api/v1/recommendations", response_model=list[RecommendationRead])
def list_recommendations(
    audit_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(get_actor),
) -> list[Recommendation]:
    statement = select(Recommendation).join(Finding)
    if audit_id:
        statement = statement.where(Finding.audit_id == audit_id)
    return list(db.scalars(statement.order_by(Recommendation.created_at.desc())).all())


@app.post("/api/v1/recommendations/{recommendation_id}/approve", response_model=RecommendationRead)
def approve_recommendation(
    recommendation_id: str,
    payload: RecommendationDecision,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> Recommendation:
    recommendation = db.get(Recommendation, recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if recommendation.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Recommendation is already {recommendation.status}")
    recommendation.status = "approved"
    recommendation.approved_by = actor
    recommendation.approved_at = datetime.now(timezone.utc)
    finding = db.get(Finding, recommendation.finding_id)
    if finding:
        db.add(AuditEvent(audit_id=finding.audit_id, event_type="recommendation.approved", actor=actor, payload={"recommendation_id": recommendation.id, "reason": payload.reason}))
    db.commit()
    db.refresh(recommendation)
    return recommendation


@app.post("/api/v1/recommendations/{recommendation_id}/reject", response_model=RecommendationRead)
def reject_recommendation(
    recommendation_id: str,
    payload: RecommendationDecision,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> Recommendation:
    recommendation = db.get(Recommendation, recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if recommendation.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Recommendation is already {recommendation.status}")
    recommendation.status = "rejected"
    finding = db.get(Finding, recommendation.finding_id)
    if finding:
        db.add(AuditEvent(audit_id=finding.audit_id, event_type="recommendation.rejected", actor=actor, payload={"recommendation_id": recommendation.id, "reason": payload.reason}))
    db.commit()
    db.refresh(recommendation)
    return recommendation


@app.get("/api/v1/projects/{project_id}/search", response_model=list[SearchResult])
def search_project(project_id: str, q: str = Query(min_length=2), db: Session = Depends(get_db), _: str = Depends(get_actor)) -> list[SearchResult]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return [
        SearchResult(chunk_id=chunk.id, page_id=chunk.page_id, url=chunk.url, content=chunk.content, score=round(score, 4))
        for chunk, score in search_chunks(db, project_id, q)
    ]
