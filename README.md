# AI Website Growth Agent

Evidence-first SEO, GEO, and AEO analysis with human-approved growth workflows.

The implementation plan and architecture decisions are documented in [README-ai-website-growth-agent.md](README-ai-website-growth-agent.md).

## Current Vertical Slice

- Next.js dashboard for starting audits and reviewing findings.
- FastAPI gateway with project, site, audit, finding, search, and approval endpoints.
- SQLAlchemy models for projects, sites, audits, pages, evidence, findings, recommendations, chunks, and audit events.
- SSRF-aware bounded crawler with same-site link discovery.
- Deterministic SEO checks for titles, descriptions, headings, canonicals, robots directives, and JSON-LD.
- NIM-compatible gateway for optional recommendation enrichment.
- Local deterministic embeddings when an NVIDIA API key is not configured.
- Hybrid lexical and embedding retrieval over stored page chunks.
- Approval endpoints that record decisions but do not publish to a CMS.
- A replaceable in-process workflow runner for local development; production should move that adapter to Temporal and LangGraph as described in the plan.
- Docker Compose services for PostgreSQL/pgvector, Redis, MinIO, API, and web.

## Local Development

Copy `.env.example` to `.env` and optionally add `NVIDIA_API_KEY` for NIM enrichment.

```bash
docker compose up --build
```

Open:

- Web dashboard: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- API health: `http://localhost:8000/health/ready`
- MinIO console: `http://localhost:9001`

To run the API without Docker on Windows:

```powershell
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r apps/api/requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

To run the frontend without Docker:

```bash
cd apps/web
npm install
npm run dev
```

## Verification

```bash
.venv/Scripts/python.exe -m pytest apps/api/tests -q
cd apps/web
npm run lint
npm run build
```

Production authentication and CMS execution are intentionally fail-closed or approval-gated in this first slice. Configure OIDC and implement a separately deployed, idempotent executor before connecting production write credentials.
