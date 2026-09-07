from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from .analyzer import analyze_page
from .crawler import crawl_site
from .db import SessionLocal
from .models import Audit, AuditEvent, DocumentChunk, Evidence, Finding, Page, Recommendation, Site
from .nim import NimGateway
from .retrieval import chunk_text, embed_text
from .settings import get_settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def collect_audit(audit: Audit, site: Site) -> None:
    settings = get_settings()
    pages = await crawl_site(site.url, settings)
    gateway = NimGateway(settings)
    db = SessionLocal()
    try:
        for page_data in pages:
            page = Page(
                audit_id=audit.id,
                url=page_data.url,
                status_code=page_data.status_code,
                title=page_data.title,
                meta_description=page_data.meta_description,
                canonical=page_data.canonical,
                h1_count=page_data.h1_count,
                structured_data_count=page_data.structured_data_count,
                noindex=page_data.noindex,
                content=page_data.content,
                content_hash=page_data.content_hash,
            )
            db.add(page)
            db.flush()

            for chunk in chunk_text(page_data.content):
                db.add(
                    DocumentChunk(
                        project_id=audit.project_id,
                        page_id=page.id,
                        url=page_data.url,
                        content=chunk,
                        token_count=max(1, len(chunk.split())),
                        embedding=await embed_text(chunk, settings),
                    )
                )

            for candidate in analyze_page(page_data):
                llm_recommendation = await gateway.recommend(candidate, page_data.content)
                recommendation_text = llm_recommendation.rationale if llm_recommendation else candidate.recommendation
                action_type = llm_recommendation.action_type if llm_recommendation else candidate.action_type
                payload = dict(candidate.payload)
                if llm_recommendation and llm_recommendation.suggested_value:
                    payload["suggested_value"] = llm_recommendation.suggested_value
                finding = Finding(
                    audit_id=audit.id,
                    page_id=page.id,
                    category=candidate.category,
                    severity=candidate.severity,
                    confidence=candidate.confidence,
                    title=candidate.title,
                    description=candidate.description,
                    recommendation=recommendation_text,
                )
                db.add(finding)
                db.flush()
                db.add(Evidence(finding_id=finding.id, page_id=page.id, url=page.url, quote=candidate.quote))
                db.add(
                    Recommendation(
                        finding_id=finding.id,
                        action_type=action_type,
                        rationale=recommendation_text,
                        payload=payload,
                    )
                )

        audit.status = "awaiting_approval" if db.scalar(select(Recommendation.id).join(Finding).where(Finding.audit_id == audit.id).limit(1)) else "completed"
        audit.completed_at = utc_now()
        db.add(AuditEvent(audit_id=audit.id, event_type="audit.completed", payload={"pages": len(pages)}))
        db.commit()
    finally:
        db.close()


def run_audit_sync(audit_id: str) -> None:
    db = SessionLocal()
    audit = db.get(Audit, audit_id)
    if not audit:
        db.close()
        return
    site = db.get(Site, audit.site_id)
    if not site:
        audit.status = "failed"
        audit.error = "Site not found"
        db.commit()
        db.close()
        return
    audit.status = "running"
    audit.started_at = utc_now()
    db.add(AuditEvent(audit_id=audit.id, event_type="audit.started"))
    db.commit()
    db.close()
    try:
        asyncio.run(collect_audit(audit, site))
    except Exception as exc:  # pragma: no cover - exercised by integration failures
        failure_db = SessionLocal()
        failed = failure_db.get(Audit, audit_id)
        if failed:
            failed.status = "failed"
            failed.error = str(exc)[:2000]
            failure_db.add(AuditEvent(audit_id=audit_id, event_type="audit.failed", payload={"error": str(exc)[:500]}))
            failure_db.commit()
        failure_db.close()
