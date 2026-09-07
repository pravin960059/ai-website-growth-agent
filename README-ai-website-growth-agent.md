# AI Website Growth Agent

> Agentic AI platform for SEO, GEO, and AEO analysis, content strategy, website optimization, and controlled growth workflows.

## Overview

AI Website Growth Agent is a full-stack AI application that turns website data, search intent, content, and technical signals into actionable growth recommendations.

The system uses a human-in-the-loop agent workflow rather than a one-shot prompt. It can inspect a website, collect structured evidence, analyze SEO/GEO/AEO opportunities, generate recommendations, propose content changes, score expected impact, and route selected actions for approval before execution.

## Goals

- Audit technical and on-page SEO signals.
- Analyze pages for AI-search visibility and answer-engine readiness.
- Identify content gaps from search intent and competitor evidence.
- Generate prioritized optimization plans.
- Produce content briefs, outlines, FAQs, metadata, and internal-link suggestions.
- Track recommendations, approvals, execution state, and outcomes.
- Keep write actions behind validation and human approval.

## Core Capabilities

### SEO

- Crawl allowed pages and inspect metadata.
- Analyze titles, descriptions, headings, canonical tags, links, indexability, and structured data.
- Detect technical and content issues.
- Score severity, confidence, and potential impact.

### GEO

Evaluate content for visibility and usefulness in generative-search experiences, including structure, evidence, entity consistency, clarity, and retrieval readiness.

### AEO

Evaluate:

- Question coverage
- Direct-answer quality
- FAQ opportunities
- Intent alignment
- Entity coverage
- Supporting evidence

### Content Intelligence

Combine page content, search terms, competitors, site structure, and business goals to create a prioritized content roadmap.

### Controlled Automation

The agent can create drafts and proposed changes, but production-facing writes should require validation, approval, and audit logging.

## Architecture

```text
                         ┌──────────────────────────┐
                         │        Next.js UI        │
                         │ Dashboard / Reports / UI │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │      FastAPI Gateway     │
                         │ Auth / API / Validation  │
                         └────────────┬─────────────┘
                                      │
                           ┌──────────┴──────────┐
                           ▼                     ▼
                ┌──────────────────┐   ┌─────────────────┐
                │ Agent Orchestrator│   │ PostgreSQL      │
                │ Planning / State  │   │ Runs / Findings │
                └─────────┬────────┘   └─────────────────┘
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
   ┌────────────┐  ┌────────────┐  ┌───────────────┐
   │ Crawl Tool │  │ Search Tool│  │ Content Tool  │
   └────────────┘  └────────────┘  └───────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ LLM / Reasoning │
                 └─────────────────┘
```

## Why Next.js?

This project has a meaningful public-web component. Next.js is useful for SSR/SEO-oriented landing pages, documentation, metadata, and the product shell. FastAPI remains responsible for AI/business logic and APIs.

## Tech Stack

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- Recharts

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- httpx

### AI

- LLM provider SDK
- Tool calling
- Agent orchestration
- Structured outputs
- Search/retrieval integrations

### Data & Infrastructure

- PostgreSQL
- Redis
- Docker / Docker Compose
- GitHub Actions

## Suggested Repository Structure

```text
ai-website-growth-agent/
├── apps/
│   ├── web/                  # Next.js
│   └── api/                  # FastAPI
├── packages/
│   ├── types/
│   └── prompts/
├── services/
│   ├── crawler/
│   ├── analyzer/
│   └── agent/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evals/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Agent Workflow

```text
1. Receive website + business goal
2. Build analysis plan
3. Gather website/search evidence
4. Normalize observations
5. Score findings
6. Generate recommendations
7. Create content/action proposals
8. Validate proposals
9. Request human approval
10. Execute approved actions
11. Record audit trail and result
```

The orchestrator controls state transitions, tool permissions, validation, retries, and approval gates. The LLM provides reasoning; it should not receive unrestricted execution authority.

## Example Finding

```json
{
  "finding": "Missing descriptive title on /pricing",
  "category": "seo",
  "severity": "medium",
  "confidence": 0.97,
  "recommendation": "Create a concise title aligned to pricing intent",
  "proposed_action": {
    "type": "update_metadata",
    "status": "pending_approval"
  }
}
```

## API Surface

```text
POST   /api/v1/projects
POST   /api/v1/audits
GET    /api/v1/audits/{audit_id}
POST   /api/v1/audits/{audit_id}/run
GET    /api/v1/findings
POST   /api/v1/recommendations/{id}/approve
POST   /api/v1/recommendations/{id}/reject
GET    /api/v1/content/opportunities
POST   /api/v1/content/drafts
GET    /health
```

## Environment

```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/website_growth
REDIS_URL=redis://localhost:6379/0
LLM_API_KEY=your_key
SEARCH_API_KEY=your_key
APP_ENV=development
API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Never commit secrets, cookies, private customer data, or production credentials.

## Local Development

```bash
git clone https://github.com/pravin960059/ai-website-growth-agent.git
cd ai-website-growth-agent
docker compose up -d postgres redis
```

API:

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

## Guardrails

- Allowlisted domains and URLs
- Typed tools instead of unrestricted HTTP/browser access
- Human approval for writes
- Idempotency keys
- Input/output schema validation
- Crawl budgets and rate limits
- Audit logs
- Prompt-injection-aware webpage handling
- Separation of untrusted content from system instructions

## Evaluation

Measure:

- Finding detection accuracy
- Recommendation usefulness
- False-positive rate
- Evidence grounding
- Tool-selection accuracy
- Action safety
- End-to-end task completion
- Latency and token usage

Build a reproducible evaluation dataset with known website issues and expected findings.

## Roadmap

### Phase 1 — Foundation

- [ ] Next.js dashboard
- [ ] FastAPI service
- [ ] PostgreSQL schema
- [ ] Authentication

### Phase 2 — Website Intelligence

- [ ] Crawler
- [ ] HTML extraction
- [ ] SEO rule engine
- [ ] Structured findings

### Phase 3 — Agent Layer

- [ ] Orchestrator
- [ ] Tool registry
- [ ] LLM tool calling
- [ ] Recommendation engine
- [ ] Approval workflow

### Phase 4 — GEO/AEO

- [ ] Intent analysis
- [ ] Answer-readiness scoring
- [ ] Generative-search checks
- [ ] Entity consistency

### Phase 5 — Content Operations

- [ ] Content briefs
- [ ] Draft generation
- [ ] Internal linking
- [ ] Publishing adapters

### Phase 6 — Production

- [ ] Evaluation suite
- [ ] Observability
- [ ] Background jobs
- [ ] CI/CD
- [ ] Deployment

## Portfolio Demo

1. Add a website.
2. Run an audit.
3. Show evidence-backed findings.
4. Ask the agent to prioritize issues.
5. Generate a content brief.
6. Approve one safe action.
7. Show the audit/action log.

## License

Add an appropriate open-source license when the repository is ready for public contribution.
