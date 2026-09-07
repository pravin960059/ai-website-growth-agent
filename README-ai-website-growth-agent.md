# AI Website Growth Agent

> An evidence-first, human-approved agent for SEO, GEO, AEO, content strategy, and controlled website optimization.

This document is the technical plan for building the product described by this repository. It explains the recommended architecture, the decision behind each major technology, the strongest alternative, and the tradeoffs being made.

The design assumes:

- The product is a multi-tenant SaaS application.
- Customers connect public websites and optional first-party data sources such as Google Search Console.
- The system may create drafts and proposed changes, but production writes require explicit human approval.
- NVIDIA NIM is the initial model platform.
- The first production deployment uses NVIDIA-hosted NIM API endpoints. Self-hosted NIM remains a supported future deployment mode for privacy, latency, or volume requirements.
- A small engineering team values operational simplicity, auditability, and safe behavior more than maximum theoretical throughput.

Documentation and model availability change quickly. Pin model IDs and package versions after evaluation, and re-check the linked NVIDIA model catalog before production rollout.

## 1. Fundamentals

### What the product does

An AI website growth agent turns website and search evidence into ranked, reviewable growth work.

It combines:

1. **Collection**: crawl allowed pages, read sitemaps, inspect metadata, collect search data, and optionally inspect competitors.
2. **Deterministic analysis**: detect facts such as missing titles, duplicate canonicals, broken links, absent structured data, and indexability problems with ordinary code.
3. **Retrieval**: find relevant pages, prior findings, search observations, business goals, and internal policies.
4. **Reasoning**: use an LLM to interpret evidence, compare alternatives, and explain impact.
5. **Planning**: turn findings into prioritized recommendations, content briefs, and proposed actions.
6. **Approval**: pause before any consequential write and ask an authorized human to approve, edit, or reject it.
7. **Execution**: apply only the approved, validated action through a narrow integration adapter.
8. **Measurement**: record what happened and compare future search, traffic, and technical signals with the baseline.

### The problems it solves

Website growth work is difficult because evidence is distributed across pages, search results, analytics, content inventories, technical configuration, and business priorities. Manual audits are slow and inconsistent. Generic LLM prompts are fast but commonly produce unsupported recommendations, miss exact technical issues, and cannot safely operate publishing systems.

The agent solves this by making evidence and state first-class objects. A recommendation is not merely text. It has source evidence, confidence, expected impact, an owner, a validation result, an approval state, an execution record, and an outcome.

### Why this is not a generic chatbot

| Generic chatbot | Website growth agent |
| --- | --- |
| Optimizes for a plausible response | Optimizes for grounded, measurable work |
| Mostly stateless conversation | Durable audit and workflow state |
| User input is the main context | Web pages and APIs are untrusted external data |
| Tools are usually optional conveniences | Tools are the evidence and action boundary |
| Text output can be accepted directly | Output must satisfy schemas and business rules |
| No inherent approval model | Human approval is a required state transition |
| Failure means a poor answer | Failure can mean an unsafe production write |

The architecture therefore has three separate concerns:

- **Control plane**: authentication, tenant policy, workflow state, approvals, idempotency, and audit logs.
- **Data plane**: crawling, parsing, indexing, search, analytics connectors, and content snapshots.
- **Reasoning plane**: NIM calls, retrieval context, tool selection, recommendation generation, and evaluation.

The LLM is a reasoning component inside those planes. It is not the system of record, the permission system, or the executor of arbitrary code.

### Product invariants

These rules should be encoded in code and tests, not left to prompts:

- No model output directly publishes to a website.
- Every finding links to one or more evidence records or is explicitly marked as heuristic.
- Every write action has a typed schema, validation result, idempotency key, approver, and audit event.
- External page content is data, never trusted instructions.
- Every crawl has an allowlist, page limit, byte limit, time limit, and rate limit.
- Every LLM run has a model, prompt version, input/output token count, latency, cost estimate, and outcome.
- Tenant filters are applied in the database query, not after retrieval in application code.
- Deterministic rules are used whenever the question can be answered without an LLM.

## 2. Architecture Overview

```text
                         Browser
                            |
                            v
                 Next.js web application
                 Dashboard / reports / approval UI
                            |
                            v
                  FastAPI application gateway
       AuthN / AuthZ / API schemas / validation / streaming
                            |
          +-----------------+------------------+
          |                                    |
          v                                    v
  Durable workflow engine                 PostgreSQL
  Temporal workflows                      System of record
  retries / timers / signals              findings / approvals / audit
          |                                    |
          v                                    +-------------------+
  LangGraph reasoning graph                     |                   |
  plan / tools / retrieval / approval           v                   v
          |                              pgvector + tsvector    Object storage
          |                              hybrid retrieval       raw HTML/snapshots
          |
          +------------+-------------+-------------+-------------+
                       |             |             |
                       v             v             v
                  Crawl tools   Search tools   CMS adapters
                  read-only     evidence       writes only after approval
                       |
                       v
                 NIM gateway
          hosted NIM API or self-hosted NIM

  Cross-cutting: Redis, OpenTelemetry, Langfuse, Prometheus/Grafana, Sentry
```

### Layer decisions

| Layer | Recommendation | Second-best alternative | Main optimization |
| --- | --- | --- | --- |
| Web UI | Next.js, React, TypeScript | Vite SPA | SEO-capable public pages plus product UI |
| API | FastAPI, Pydantic, SQLAlchemy | NestJS | Python AI and crawling ecosystem with typed HTTP APIs |
| System of record | PostgreSQL | MongoDB or separate workflow database | Relational integrity, tenant filters, auditability |
| Vector search | pgvector plus PostgreSQL full text | Qdrant | One transactional store and simpler operations |
| Durable workflows | Temporal | Celery plus Redis | Durable waits, retries, approvals, and replay |
| Agent graph | LangGraph with explicit nodes | CrewAI or an unrestricted ReAct loop | State visibility and controlled tool execution |
| LLM | NIM-hosted Llama 3.3 70B plus a smaller model | A single model or another hosted provider | Tool use, model choice, and a stable OpenAI-compatible boundary |
| Embeddings | NVIDIA NeMo Retriever NIM | A local sentence-transformer | Consistent NVIDIA model lifecycle and retrieval quality |
| Deployment | Docker plus managed containers | Kubernetes from day one | Low operational burden until GPU self-hosting is justified |
| Observability | OpenTelemetry plus Langfuse, Prometheus, Sentry | LangSmith-only | Vendor-neutral traces plus LLM-specific debugging |
| Authentication | OIDC provider plus FastAPI JWT validation | Self-managed Keycloak | Standard federation without owning identity operations |

### Trust boundaries

1. The browser is untrusted and never receives the NIM API key, CMS refresh token, or database credentials.
2. The API authenticates the user and establishes tenant context before calling application services.
3. The crawler treats every downloaded page as hostile input. HTML may contain prompt injection, tracking URLs, oversized content, or SSRF targets.
4. The reasoning graph receives labeled evidence, not raw unrestricted network access.
5. The executor is a separate privileged boundary. It accepts only approved action records, not free-form model text.

## 3. Frontend and API Boundary

### Recommendation: Next.js plus FastAPI

**Next.js** is a React framework that provides server rendering, routing, metadata handling, and client-side application features. It is the right fit because the product has both public SEO-sensitive pages and an authenticated dashboard. Public marketing, documentation, and report-sharing pages can be rendered and indexed efficiently, while the dashboard can use normal React interactions.

Use:

- Next.js App Router.
- TypeScript with shared API types generated from the FastAPI OpenAPI schema.
- TanStack Query for server-state fetching, caching, invalidation, and mutation status.
- Tailwind CSS only if the team wants utility-first styling; keep the design system in components rather than embedding business logic in class strings.
- Recharts for simple audit trend and opportunity charts. Use a specialized visualization library only when graph or large-timeseries requirements appear.

**FastAPI** is a Python ASGI framework that generates OpenAPI schemas from typed route definitions. It is the right backend because the product needs Python libraries for crawling, HTML processing, embeddings, evaluation, and NIM clients. Pydantic models make API contracts and tool schemas explicit.

The API should own:

- Authentication and authorization checks.
- Request validation and idempotency keys.
- Project, audit, finding, recommendation, approval, and report endpoints.
- Starting and querying workflows.
- Streaming run events to the UI.
- No long-running crawl or LLM loop directly inside a request handler.

### Why not a single Next.js backend?

Next.js route handlers could serve a small product, but combining the browser server, crawling, AI orchestration, and privileged integrations makes dependency boundaries and worker scaling less clear. It also forces Python functionality behind a second process later. Keeping Next.js as the presentation layer and FastAPI as the application gateway makes the deployment and security boundaries explicit.

### Why not NestJS?

NestJS is a strong alternative for a TypeScript-only organization. It loses here because the core work is Python-heavy and the repository already specifies Python, FastAPI, SQLAlchemy, and httpx. Choosing NestJS would optimize language uniformity at the expense of duplicating or wrapping Python crawler and evaluation libraries.

### Tradeoffs

- Two languages and two build systems increase repository complexity.
- The split allows each side to use its strongest ecosystem and lets frontend and backend scale independently.
- Shared types should be generated from OpenAPI rather than manually maintained in two languages.

## 4. Data Model and Storage

### Recommendation: PostgreSQL as the system of record

PostgreSQL is a relational database. It should hold all business entities and state transitions:

```text
tenants
users
memberships
projects
sites
connectors
crawl_runs
pages
page_versions
search_observations
analytics_observations
documents
document_chunks
findings
evidence
recommendations
approvals
actions
workflow_runs
usage_events
audit_events
```

Every tenant-owned table should contain `tenant_id`. Every query path should require tenant context. Use foreign keys, unique constraints, check constraints, and database transactions for state changes.

Use SQLAlchemy 2 for database access, Alembic for migrations, and `psycopg` for PostgreSQL connectivity. Keep ORM models separate from API schemas and domain commands.

### Object storage

Store large immutable artifacts in S3-compatible object storage:

- Raw HTML responses.
- Rendered HTML when a browser was required.
- Sitemap files and response headers.
- Crawl manifests.
- Search result snapshots.
- Generated reports and exports.

Store only the object key, content hash, metadata, and retention information in PostgreSQL. Do not put unbounded HTML bodies in ordinary finding rows.

Use MinIO in local development and S3, GCS, or Azure Blob in production. The interface should be an application-owned `BlobStore` protocol so the rest of the code does not depend on a provider.

### Redis

Redis is an in-memory key-value store. Use it for:

- Rate-limit counters and token buckets.
- Short-lived crawl locks.
- Small response caches.
- Pub/sub or stream notifications when appropriate.

Do not use Redis as the only workflow state store or audit log. Redis data loss must not erase an approval or a production action.

### Why not MongoDB?

MongoDB would make variable JSON observations easy to store, but the product has strong relationships and state transitions: a recommendation belongs to a finding, an approval belongs to an action, and an action must have a durable audit trail. PostgreSQL JSONB columns provide flexible raw payloads without giving up joins, transactions, constraints, and reporting.

### Tradeoffs

- PostgreSQL becomes a critical dependency and must be backed up and monitored.
- A single system of record is operationally simpler and makes tenant filtering safer.
- High-volume raw artifacts stay outside PostgreSQL so backups and indexes remain manageable.

## 5. Website Data Pipeline

### Pipeline stages

```text
project configuration
    -> crawl plan
    -> robots.txt and sitemap policy
    -> bounded fetch
    -> raw snapshot
    -> HTML normalization
    -> deterministic extraction
    -> page version and content hash
    -> rule findings
    -> chunking and embedding
    -> retrieval index
    -> agent evidence bundle
```

### Fetching strategy

Use an application-owned crawler built around `httpx` for normal HTTP pages. `httpx` is an async Python HTTP client with explicit timeout, redirect, proxy, and connection-pool controls.

The crawler must enforce:

- Approved scheme: HTTPS by default; HTTP only when explicitly allowed.
- Domain and URL allowlists.
- `robots.txt` handling according to [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309).
- Sitemap discovery and sitemap URL limits.
- Per-host concurrency and delay.
- Maximum pages, response bytes, redirect hops, and total duration.
- Content-type checks before parsing.
- DNS resolution and private-address checks to prevent SSRF.
- `ETag` and `Last-Modified` conditional requests where supported.
- Content hashing to skip unchanged processing.

Use Playwright only as a bounded fallback for pages whose meaningful content is rendered by JavaScript. Run browser workers in a sandbox with a separate network policy. Do not give the LLM arbitrary browser access.

### Parsing and normalization

Use deterministic HTML processing before any model call:

- Parse with a standards-compatible HTML parser such as `selectolax` or `lxml`.
- Extract title, meta description, canonical, robots directives, hreflang, headings, links, images, JSON-LD, Open Graph, and visible text.
- Preserve the DOM section path for each text chunk: `H1 > H2 > H3`.
- Normalize URLs, remove tracking parameters for comparison, and retain the original URL for evidence.
- Detect duplicate or conflicting metadata with code.
- Keep raw and normalized representations so parser changes can reprocess old snapshots.

The rule engine should create high-confidence findings without an LLM. For example, missing title, multiple H1 elements, broken internal links, and absent canonical tags are deterministic facts.

### External data sources

Implement connectors behind interfaces:

- Google Search Console for queries, impressions, clicks, CTR, and average position.
- Google Analytics 4 or another analytics provider for conversion and engagement outcomes.
- A SERP provider for repeatable rank and competitor observations.
- CMS adapters for proposed and approved writes.

First-party data should be preferred over scraped approximations. Search APIs and analytics APIs have different terms, quotas, and freshness guarantees; store the provider, request time, query parameters, and raw response hash with every observation.

The added DuckDuckGo MCP server is useful for developer research and exploratory evidence gathering. It should not be the production SERP source because its public endpoint, rate limits, result stability, and terms are not a durable product contract. Production search should use a licensed API or customer-provided Search Console data.

### Why not crawl everything with a browser?

Browser crawling is slower, more expensive, harder to isolate, and more exposed to page scripts. HTTP fetching handles most content and makes request policy easier to inspect. Browser rendering is a targeted fallback, not the default data path.

## 6. Retrieval and Vector Search

### What retrieval is

Retrieval-Augmented Generation, or RAG, means selecting relevant evidence at request time and placing that evidence in the LLM context. It prevents the model from relying only on stale training data or a huge undifferentiated prompt.

### Recommendation: PostgreSQL plus pgvector and hybrid retrieval

[pgvector](https://github.com/pgvector/pgvector) adds vector similarity search to PostgreSQL. Use it beside PostgreSQL full-text search rather than creating a separate vector service in the first production version.

Use:

- `tsvector` and GIN indexes for exact terms, URLs, product names, entities, and error codes.
- `pgvector` HNSW indexes for semantic similarity.
- Metadata filters for `tenant_id`, project, site, language, source type, page version, and freshness.
- Reciprocal Rank Fusion or a weighted rank merge to combine lexical and semantic results.
- Optional second-stage reranking after retrieval quality is measured.

The initial chunk schema should look conceptually like:

```sql
document_chunks (
  id uuid primary key,
  tenant_id uuid not null,
  project_id uuid not null,
  page_version_id uuid,
  source_type text not null,
  url text,
  heading_path text,
  content text not null,
  search_vector tsvector generated always as (... ) stored,
  embedding vector(2048),
  content_hash text not null,
  token_count integer not null,
  created_at timestamptz not null
)
```

The exact generated-column expression and dimension must be implemented in a migration. `nvidia/nemotron-3-embed-1b` is the recommended starting embedding model because the current NeMo Retriever support matrix lists 2048-dimensional output and a validated 4096-token maximum sequence length. Pin the model ID and re-run retrieval evaluations if NVIDIA changes availability.

Start with section-aware chunks of roughly 400-800 tokens and 50-100 tokens of overlap. These are starting parameters, not laws. Measure recall on the product's gold questions and adjust. Never split a heading from the section it describes when the DOM structure can preserve it.

### Retrieval request flow

1. Normalize the question into a retrieval query without changing the original user intent.
2. Apply tenant, project, source, language, and freshness filters in SQL.
3. Run lexical and vector retrieval independently.
4. Merge ranks and remove duplicate chunks from the same page section.
5. Rerank the top candidate set when the evaluation suite shows a measurable gain.
6. Return chunks with stable evidence IDs, URLs, headings, content hashes, and retrieval scores.
7. Put only the selected evidence into the model prompt.

### Why not traditional search only?

BM25 or PostgreSQL full-text search is excellent for exact terms such as `/pricing`, schema property names, error messages, and brand names. It is weaker when a user asks for an idea using words different from the source page. It remains one half of the recommended hybrid design.

### Why not vector search only?

Dense retrieval can miss exact URLs, product codes, named entities, and short technical terms. It can also return semantically similar but legally or operationally different pages. Hybrid retrieval is more robust for SEO evidence because both meaning and exact strings matter.

### Second-best vector alternative: Qdrant

[Qdrant](https://qdrant.tech/) is a dedicated vector database with strong filtering and vector-native operations. It becomes the better choice when the index is much larger than the transactional database, vector queries require independent scaling, or a platform team already operates it.

It loses for this first version because it creates a second consistency boundary: page versions and chunks live in PostgreSQL while vectors live in Qdrant. Deletes, tenant filters, re-indexing, backups, and migrations become distributed operations. pgvector optimizes for fewer moving parts and transactional joins, not maximum independent vector scale.

### Embedding tradeoffs

- A 1B embedding model costs more than a small sentence transformer but can improve domain retrieval and keeps the initial model boundary inside NVIDIA NIM.
- A smaller `llama-nemotron-embed-300m-v2` candidate can reduce cost and latency, but it must beat the 1B model on the project's retrieval set before promotion.
- The older `nv-embedqa-e5-v5` has useful published retrieval results and 1024-dimensional output, but current support documentation marks it as an older/deprecated path. Do not start a new design on it without a deliberate compatibility reason.
- Embeddings can contain sensitive information. Treat them as tenant data and delete them when their source is deleted.

## 7. NVIDIA NIM and LLM Selection

### What NIM is

[NVIDIA NIM](https://docs.api.nvidia.com/nim/docs/introduction) is a set of containerized, optimized inference microservices. NIM can be consumed as a hosted API or self-hosted on NVIDIA GPU infrastructure. Both modes expose industry-standard APIs, which lets the application keep the same model gateway while changing deployment mode.

The current NIM LLM API is OpenAI-compatible. The API reference documents chat completions, streaming, model discovery, health endpoints, tokenization, and NIM management endpoints. The hosted API base is documented as `https://integrate.api.nvidia.com`, with `/v1/chat/completions` as the main inference endpoint.

### Recommendation: a small model portfolio, not one universal model

Use a model registry controlled by configuration:

| Role | Initial model | Work | Why |
| --- | --- | --- | --- |
| Primary reasoning | `meta/llama-3.3-70b-instruct` | Evidence synthesis, prioritization, complex recommendations | Model card lists 128k context, commercial use readiness, function-calling capability, and strong instruction-following benchmarks |
| Fast extraction | `meta/llama-3.1-8b-instruct` | Classification, short metadata extraction, simple normalization | Lower latency and lower resource usage; adequate for bounded structured tasks |
| Advanced challenger | Current Nemotron or other catalog model selected by evaluation | Difficult synthesis, ambiguous prioritization, or multilingual cases | Test against the primary model instead of assuming a larger model is better |
| Embedding | `nvidia/nemotron-3-embed-1b` | Page and evidence embeddings | Current support matrix documents 2048 dimensions and 4096-token validation |

The primary recommendation is based on the [Llama 3.3 70B NIM model card](https://build.nvidia.com/meta/llama-3_3-70b-instruct). Model IDs, availability, context limits, and pricing can change, so the model registry must be editable without a code deployment.

### Why not use the largest available model for every call?

Large models increase latency, cost, queue pressure, and failure impact. Much of an audit is deterministic extraction or short classification. Routing small bounded tasks to a smaller model leaves the larger model for decisions where its reasoning quality matters.

### Why not use only the 8B model?

An 8B model is attractive for cost and latency, but complex evidence comparison, prioritization, and tool selection are the highest-risk quality steps. It should be a fast path and fallback, not the default for every recommendation until evaluation proves equivalence.

### Why not select a model by benchmark score alone?

Public benchmarks do not measure this product's requirements: evidence citation, SEO issue precision, safe tool selection, tenant isolation, and approval behavior. Model promotion must require a task-specific evaluation set.

### NIM integration

Hide provider-specific details behind `NimClient` and `ModelGateway` interfaces. The hosted implementation can use the OpenAI Python SDK because NIM exposes the OpenAI-compatible protocol:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=settings.nvidia_api_key,
    base_url=settings.nvidia_nim_base_url,
    timeout=settings.nim_timeout_seconds,
    max_retries=0,  # retries belong in the gateway policy
)

response = await client.chat.completions.create(
    model=settings.nim_primary_model,
    messages=messages,
    tools=tools,
    tool_choice="auto",
    temperature=0.1,
    max_tokens=1500,
)
```

Use a base URL that already includes `/v1`, for example:

```text
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_PRIMARY_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_NIM_FAST_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_NIM_EMBED_MODEL=nvidia/nemotron-3-embed-1b
```

The [NIM API reference](https://docs.nvidia.com/nim/large-language-models/latest/reference/api-reference.html) documents the OpenAI-compatible routes. For self-hosted NIM, point the same gateway at the internal service URL and use NIM health endpoints for readiness checks.

### Token limits and context management

The model context limit is not the application's context budget. A 128k model should not receive an entire crawl. Large prompts increase cost, latency, distraction, and prompt-injection exposure.

Use these starting application budgets:

| Operation | Input target | Output cap | Context policy |
| --- | ---: | ---: | --- |
| Metadata extraction | 4,000 tokens | 512 | One page and deterministic metadata |
| Finding explanation | 8,000 tokens | 1,000 | Finding plus only supporting evidence |
| Prioritization | 16,000 tokens | 1,500 | Top findings, business goals, constraints |
| Content brief | 24,000 tokens | 2,500 | Intent, page evidence, competitors, internal links |
| Report synthesis | 32,000 tokens | 4,000 | Selected evidence and aggregated findings |

Reserve at least 20-25 percent of the model context for output and protocol overhead. Count tokens before requests. Self-hosted NIM exposes tokenization and message token-counting endpoints; hosted behavior must be verified for the selected model, otherwise use the model's tokenizer package and conservative margins.

Use `max_tokens` on every request. Set temperature near zero for extraction and scoring. Use a moderate temperature only for drafts where multiple phrasings are useful. Never allow a loop to increase its own token or step budget.

### Structured output

Every model result that feeds code should be validated against a Pydantic schema. NIM supports structured generation; its documentation recommends `guided_json` for constrained JSON when the deployment supports the relevant backend. Do not rely on `response_format={"type": "json_object"}` alone because valid JSON can still be the wrong shape.

The safe sequence is:

1. Ask for a known schema.
2. Validate the response with Pydantic.
3. Reject unknown or dangerous fields.
4. Retry once with a compact validation error if appropriate.
5. Store the failed response and stop rather than silently repairing an unsafe action.

Treat `guided_json` as a capability discovered per model/deployment. Hosted and self-hosted NIM versions may differ.

### Tool calling and MCP

NIM does not directly connect to MCP servers. The application connects to an MCP server, translates the tool schema to the OpenAI `tools` format, sends it to NIM, executes the returned tool call, and sends the tool result back to the model. The application remains the policy enforcement point.

For self-hosted NIM tool calling, the NIM documentation requires `--enable-auto-tool-choice` and a model-compatible `--tool-call-parser`, such as `llama3_json` for supported Llama models. Test tool calls in the exact deployed profile; a model that writes plausible tool-call text is not equivalent to a parsed tool call.

### Cost model

Do not hardcode a public per-token price into the application. NVIDIA hosted API availability, credits, quotas, and commercial terms are account and model dependent. Measure actual usage and keep pricing configuration separate from model configuration.

Record for every generation:

- Provider and model ID.
- Prompt and completion token counts.
- Cache or batch status if available.
- Retry count.
- Duration and time to first token.
- Estimated cost using the current provider rate card.
- Tenant and project attribution.

For self-hosted NIM, the cost model is GPU-hours, storage, networking, NVIDIA AI Enterprise entitlement where applicable, on-call time, and capacity reserved for peaks. Self-hosting is not automatically cheaper; it becomes compelling when utilization, privacy, latency, or contractual requirements justify owning GPU operations.

## 8. Agentic Framework and Reasoning Loop

### Recommendation: LangGraph inside Temporal

[LangGraph](https://github.com/langchain-ai/langgraph) is a graph-based runtime for stateful LLM applications. Use it for one agent run's reasoning graph: typed state, explicit nodes, tool routing, streaming, checkpoints, and human interrupts.

[Temporal](https://temporal.io/) is a durable workflow engine. Use it for the outer lifecycle: long crawls, retries, scheduled audits, approval waits, deadlines, escalations, and resumability across deployments.

This split avoids asking one framework to solve two different problems:

- Temporal owns durable business process state.
- LangGraph owns LLM reasoning state.
- PostgreSQL owns business records and audit rows.
- Redis owns ephemeral coordination and rate limits.

### Graph design

```text
start
  -> validate_request
  -> build_plan
  -> gather_evidence
  -> normalize_observations
  -> run_deterministic_rules
  -> retrieve_context
  -> analyze_findings
  -> rank_opportunities
  -> draft_recommendations
  -> validate_recommendations
  -> approval_interrupt
  -> execute_approved_actions
  -> verify_results
  -> record_outcome
  -> complete
```

The graph should use bounded loops. For example, the evidence node may ask for one more search query when evidence is insufficient, but it must have a maximum query count and a reason code for stopping.

LangGraph's `interrupt()` primitive pauses execution and persists graph state until a human resumes it. Use a durable checkpointer in production and a stable `thread_id` derived from the workflow run. The UI should show the approval payload as a structured recommendation, not expose arbitrary serialized state.

### Tool policy

Tools should be typed Python functions or application-owned adapters. Initial tools:

- `get_site_config`: read project policy and crawl budget.
- `crawl_urls`: read-only bounded fetch operation.
- `get_page_observations`: query normalized page facts.
- `search_index`: hybrid retrieval with tenant filters.
- `get_search_console_data`: read-only first-party metrics.
- `search_serp`: bounded licensed search provider request.
- `create_content_brief`: draft-only operation.
- `validate_metadata_change`: deterministic validation.
- `propose_cms_change`: creates a pending action, never publishes.
- `publish_approved_change`: privileged executor called only after authorization checks.
- `verify_published_change`: read-after-write validation.

Every tool definition must include its input schema, output schema, permission class, cost class, timeout, retry policy, and whether it is read-only. Tool results must carry evidence IDs where applicable.

### Why not an unrestricted ReAct loop?

ReAct-style loops let a model alternate between reasoning and tools, but an unbounded loop is difficult to audit and can repeatedly search, spend tokens, or call the wrong integration. A graph exposes the allowed states and makes it possible to test each transition.

### Why not CrewAI or a multi-agent swarm?

CrewAI and similar role-oriented frameworks can be useful when independent specialists genuinely need separate goals and communication. This product initially has one evidence model, one approval policy, and one audit trail. Multiple agents would add coordination, duplicated context, more model calls, and more difficult attribution without proving better findings. Add specialist subgraphs only after evaluation shows a concrete gain.

### Why not a custom state machine only?

A hand-built state machine is a reasonable second choice for a very small fixed workflow. LangGraph loses some dependency simplicity, but provides tested interruption, streaming, checkpointing, and tool-loop primitives. Keep the domain graph in application code so migration remains possible.

## 9. Authentication and External API Integration

### User authentication

Use an OIDC-compatible identity provider. OIDC is an authentication standard layered on OAuth 2.0. The provider handles login, MFA, password recovery, and federation; FastAPI validates signed access tokens and maps the subject to a local user and tenant membership.

Recommended authorization model:

- Provider identity proves who the user is.
- Local membership tables decide which tenant and project resources the user can access.
- Roles such as owner, editor, analyst, approver, and viewer control actions.
- Approval authority is checked at the moment of approval, not only when the screen loads.
- Service-to-service calls use short-lived workload credentials or signed internal tokens.

Keycloak is the second-best alternative when self-hosting identity is mandatory. It loses for a small team because upgrades, availability, federation, and security response become another production system.

### NIM credentials

- Store `NVIDIA_API_KEY` only in a secret manager in production.
- Load it on the server or worker process, never in browser JavaScript.
- Never store it in PostgreSQL, workflow payloads, prompts, logs, traces, or error messages.
- Rotate it without redeploying application code when the secret manager supports versioned secrets.
- Use a separate development key and production key.
- Restrict egress so only approved NIM and integration endpoints are reachable from workers.

The hosted NIM API key is an application credential, not a tenant credential. If tenants eventually bring their own provider keys, encrypt them with envelope encryption and keep them outside workflow histories.

### Rate limits and retries

Use a Redis-backed token bucket per provider, model, tenant, and operation class. A crawl and an LLM request need separate budgets.

Retry policy:

- Retry connection resets, timeouts, and 5xx responses with exponential backoff and jitter.
- Respect `Retry-After` for 429 responses.
- Do not blindly retry non-idempotent external writes.
- Use an idempotency key for every action and external mutation.
- Cap retries and record the final reason.
- Open a circuit breaker when a provider is unhealthy.

Fallback order:

1. Retry the same model only for transient errors.
2. Route bounded work to the fast NIM model when the primary model is unavailable.
3. Complete deterministic SEO rules without LLM enrichment.
4. Mark the run `partial` and ask for a retry if the missing reasoning is material.

Do not silently switch to another provider for customer data. A cross-provider fallback is an explicit compliance and data-processing decision.

### External content and prompt injection

The website being audited is an attacker-controlled input from the model's point of view. The crawler must label retrieved content as `UNTRUSTED_WEB_CONTENT` and keep it structurally separate from system policy and user intent.

Apply defense in depth:

- Strip scripts and hidden text before analysis while retaining raw evidence outside the prompt.
- Never interpret instructions found in pages as tool policy.
- Use allowlisted tools and server-side authorization.
- Limit what information can be returned from tools.
- Validate model outputs and proposed actions.
- Require humans for writes.
- Test indirect prompt-injection fixtures regularly.

This follows the [OWASP LLM01:2025 Prompt Injection guidance](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), which specifically identifies external web content as an indirect injection source.

## 10. Deployment Infrastructure

### Development

Use Docker Compose for local dependencies:

- PostgreSQL with pgvector.
- Redis.
- MinIO.
- Temporal development server.
- Optional local NIM only when an NVIDIA GPU is available.

Run the web and API locally with hot reload. Do not require a GPU for ordinary development; use the hosted NIM endpoint through a development key.

### Production recommendation: managed containers first

Package the web, API, crawler workers, agent workers, and executor as separate images. Deploy them on a managed container platform such as AWS ECS Fargate, Google Cloud Run, or Azure Container Apps. Use managed PostgreSQL, Redis, object storage, and Temporal Cloud or a managed Temporal-compatible service.

An AWS reference deployment would be:

- Next.js on Vercel or a container behind a CDN.
- FastAPI on ECS Fargate.
- Separate ECS worker services for crawl, analysis, and execution.
- RDS PostgreSQL with pgvector support.
- ElastiCache Redis.
- S3 for snapshots.
- Temporal Cloud for durable workflow execution.
- Secrets Manager plus KMS.
- OpenTelemetry collector and a managed or self-hosted observability stack.

The choice is the deployment shape, not the cloud brand. Keep providers behind interfaces where practical.

### Why not Kubernetes first?

Kubernetes becomes attractive when the team must self-host NIM on GPUs, operate many services, or control scheduling and multi-region infrastructure. It is the second-best initial choice because it adds cluster upgrades, ingress, autoscaling, storage, GPU scheduling, and security policy before the product has validated demand. Managed containers optimize for a small team's delivery speed and lower operational risk.

### Self-hosted NIM path

Move NIM behind an internal service boundary when any of these conditions are true:

- Hosted NIM data-processing terms do not meet a customer's requirements.
- Request volume makes dedicated GPUs cheaper than hosted usage.
- Tail latency or network locality is a product requirement.
- The model must be customized or served with internal assets.

Self-hosted NIM requires NVIDIA GPU-compatible infrastructure, NGC access, model cache storage, readiness and liveness checks, and GPU capacity planning. Use NIM's `/v1/health/live`, `/v1/health/ready`, `/v1/models`, and `/v1/metrics` endpoints. Keep the NIM service private; only the model gateway can call it.

### Container practices

- Use multi-stage builds and pinned lockfiles.
- Run as a non-root user.
- Use read-only root filesystems where possible.
- Set CPU, memory, and ephemeral storage limits.
- Do not put secrets in images or build logs.
- Scan images and dependencies in CI.
- Use separate deployment identities for web, API, workers, and executor.
- Run database migrations as a controlled release step, not on every application startup.

### CI/CD

GitHub Actions should run:

1. Formatting, linting, type checking, and unit tests.
2. API contract and migration tests.
3. Retrieval and agent evaluation subsets.
4. Container build and vulnerability scan.
5. Deployment to staging through cloud OIDC rather than long-lived cloud keys.
6. Smoke tests against staging.
7. A manual production approval for schema or executor changes.

Use [GitHub Actions OIDC](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-cloud-providers) for cloud authentication.

## 11. Monitoring and Observability

### Recommendation: OpenTelemetry plus specialized tools

[OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai) provide a vendor-neutral vocabulary for LLM calls, agent steps, retrieval, and tool execution.

Use:

- OpenTelemetry for traces, metrics, and propagation.
- [Langfuse](https://langfuse.com/docs/observability/overview) for prompt/version tracking, generation traces, token usage, cost attribution, and evaluation scores.
- Prometheus and Grafana for service and infrastructure metrics.
- Sentry for application exceptions and release correlation.
- Structured JSON logs shipped to a managed log platform.

LangSmith is the second-best alternative because it integrates well with LangGraph and is convenient for teams already using the LangChain platform. It loses as the default because Langfuse can be self-hosted and keeps the observability choice more vendor-neutral for a NIM-centered stack. Either is acceptable if the team already operates one.

### Trace structure

One audit trace should contain spans for:

```text
audit.run
  workflow.plan
  crawl.fetch
  parse.page
  rule.evaluate
  retrieval.lexical
  retrieval.vector
  retrieval.rerank
  llm.generate
  tool.execute
  approval.wait
  action.execute
  action.verify
```

Attach metadata, not secrets:

- Tenant and project IDs, preferably pseudonymous.
- Workflow and audit IDs.
- Model and provider.
- Prompt version.
- Token counts and estimated cost.
- Retrieval query and evidence IDs.
- Tool name, permission class, and result status.
- Retry and timeout data.
- Evaluation scores.

Redact API keys, cookies, authorization headers, refresh tokens, and unnecessary full page contents. Keep full prompts and outputs behind a separate access-controlled debugging policy with a short retention period.

### Metrics that matter

**Product quality**

- Finding precision, recall, and false-positive rate by category.
- Evidence citation coverage.
- Retrieval recall@k and MRR on a gold query set.
- Recommendation acceptance and edit rate.
- Approval rejection rate and rejection reasons.
- Safe-action validation failure rate.
- Post-change improvement where a reliable baseline exists.

**Reliability**

- Audit completion rate.
- Partial and failed run rate.
- Crawl success rate by host.
- Tool-call validation failures.
- NIM 429, 4xx, 5xx, and timeout rates.
- Queue age and workflow duration.
- Approval wait time.

**Performance and cost**

- API p50/p95/p99 latency.
- LLM time to first token and total generation time.
- Input/output tokens per audit.
- Calls per audit and retries per audit.
- Cost per completed audit and cost per accepted recommendation.
- Embedding throughput and index latency.
- Database connection pool utilization.

**Security**

- SSRF blocks.
- Prompt-injection detections.
- Denied tool calls.
- Cross-tenant authorization failures.
- Secret-scanning and dependency findings.
- Writes attempted without approval.

### Alert examples

- Page crawl failures exceed 20 percent for a host over 15 minutes.
- NIM 5xx or timeout rate exceeds 5 percent.
- Cost per audit exceeds the configured budget.
- Any production write lacks a matching approved action.
- Cross-tenant authorization check fails once.
- Retrieval recall regression exceeds the evaluation threshold.
- Workflow queue age exceeds the customer-facing SLA.

## 12. Security, Privacy, and Data Handling

### Data classification

Classify data before sending it to NIM or storing it:

- Public page content.
- Customer business goals and strategy.
- Search and analytics data.
- Credentials and refresh tokens.
- Draft content and approved actions.
- Audit and security logs.

Public does not mean harmless. Page content can contain customer information, hidden instructions, or proprietary copy. Credentials and tokens must never enter model context.

### Network security

- Enforce outbound host allowlists for crawler and connector workers.
- Resolve DNS and reject loopback, link-local, private, reserved, and metadata-service addresses.
- Re-check every redirect target.
- Use separate egress policies for crawl, NIM, analytics, and CMS workers.
- Use private network paths for PostgreSQL, Redis, object storage, and self-hosted NIM.
- Terminate TLS at the edge and validate certificates for outbound calls.

### Authorization and privileged writes

The model must not possess CMS credentials. The executor retrieves a credential only after:

1. The action record exists and is still pending approval.
2. The approver is authorized for the tenant and action type.
3. The action payload passes deterministic validation.
4. The idempotency key has not already been completed.
5. The target URL or object is still in the project allowlist.
6. A final policy check permits the operation.

Separate read-only and write-capable workers. A compromise in the crawler or reasoning worker must not directly publish content.

### Retention

Recommended defaults:

- Raw crawl snapshots: 30-90 days, configurable per tenant.
- Normalized pages and findings: retained while the project is active.
- LLM prompts and completions: short retention, such as 7-30 days, unless the customer opts into longer debugging history.
- Audit events and approvals: retained according to contractual and legal requirements.
- Credentials: retained only until revoked or disconnected, encrypted at rest.

Deletion must cascade through raw objects, chunks, embeddings, search observations, and derived reports. A deleted page must not remain discoverable through a vector index.

### Compliance decisions

Before selling to regulated customers, review:

- NVIDIA hosted API terms, data retention, training-use, and regional processing terms.
- Model licenses for every selected model.
- Customer data-processing agreements.
- GDPR deletion and access requirements where applicable.
- SOC 2 control evidence if enterprise buyers require it.

If hosted processing is unacceptable, self-hosted NIM reduces provider exposure but does not remove the application's own security, privacy, and model-license obligations.

## 13. API and Domain Design

Keep the public API resource-oriented and expose workflow state explicitly:

```text
POST   /api/v1/projects
POST   /api/v1/sites
POST   /api/v1/audits
POST   /api/v1/audits/{audit_id}/run
GET    /api/v1/audits/{audit_id}
GET    /api/v1/audits/{audit_id}/events
GET    /api/v1/findings
GET    /api/v1/recommendations
POST   /api/v1/recommendations/{id}/approve
POST   /api/v1/recommendations/{id}/reject
POST   /api/v1/recommendations/{id}/edit
GET    /api/v1/content/opportunities
POST   /api/v1/content/drafts
POST   /api/v1/connectors/search-console
POST   /api/v1/connectors/cms
GET    /health/live
GET    /health/ready
```

Use explicit status values:

```text
queued -> running -> awaiting_approval -> approved -> executing -> verified -> completed
                         |                 |
                         v                 v
                      rejected           failed
```

Use `Idempotency-Key` on audit creation, workflow starts, approvals, and action execution. Return a stable run ID immediately for long-running operations. Stream progress through Server-Sent Events or WebSockets only as a projection of persisted workflow events; do not make the connection itself the source of state.

## 14. Evaluation Strategy

AI quality needs a regression suite, not only unit tests.

### Gold dataset

Create fixtures containing:

- Known technical SEO issues.
- Pages with correct and incorrect metadata.
- Duplicate and conflicting structured data.
- Search-intent examples with expected classifications.
- GEO/AEO examples with evidence requirements.
- Benign pages containing indirect prompt-injection text.
- Content briefs with human-accepted reference answers.
- Approved and rejected action examples.

Each case should record the expected finding type, evidence source, severity range, confidence requirement, and whether an action is allowed.

### Metrics

- Rule precision and recall.
- Retrieval recall@k, MRR, and citation coverage.
- Finding precision, recall, and calibration.
- Recommendation acceptance and edit distance.
- Tool-selection accuracy.
- Structured-output validity rate.
- Unauthorized-action rate, which must be zero.
- P50/p95 latency and token use.
- Cost per successful workflow.

Use deterministic assertions for safety and schema tests. Use an LLM judge only as a supplemental signal for qualitative usefulness, never as the only approval gate.

### Model and prompt promotion

Store prompt templates and model routing policy with version identifiers. Run candidate models against the same dataset. Promote only when the candidate improves the required quality metrics without violating cost, latency, or safety thresholds. Keep a rollback configuration for the prior model.

## 15. Repository Structure

```text
ai-website-growth-agent/
├── apps/
│   ├── web/                         # Next.js application
│   └── api/                         # FastAPI gateway and domain services
├── packages/
│   ├── types/                       # Generated/shared API types
│   └── prompts/                     # Versioned prompt templates and schemas
├── services/
│   ├── crawl/                       # Bounded HTTP/browser workers
│   ├── analysis/                    # Parsers and deterministic rules
│   ├── retrieval/                   # Chunking, embeddings, hybrid search
│   ├── agent/                       # LangGraph graphs and model gateway
│   ├── workflows/                   # Temporal workflows and activities
│   └── executor/                    # Approval-gated CMS actions
├── db/
│   ├── migrations/
│   └── seeds/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── workflows/
│   └── evals/
├── infra/
│   ├── docker/
│   ├── terraform/
│   └── observability/
├── docs/
├── docker-compose.yml
├── .env.example
└── README-ai-website-growth-agent.md
```

## 16. Configuration

Development configuration should be explicit and safe:

```bash
APP_ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/website_growth
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_BUCKET=website-snapshots
TEMPORAL_TARGET=localhost:7233

NVIDIA_API_KEY=replace_me
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_PRIMARY_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_NIM_FAST_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_NIM_EMBED_MODEL=nvidia/nemotron-3-embed-1b

SEARCH_PROVIDER=licensed_provider
SEARCH_API_KEY=replace_me
OIDC_ISSUER_URL=https://identity.example.com/
OIDC_AUDIENCE=website-growth-api

MAX_PAGES_PER_AUDIT=500
MAX_CRAWL_BYTES=524288000
MAX_AGENT_STEPS=24
MAX_LLM_CALLS_PER_AUDIT=40
MAX_INPUT_TOKENS_PER_AUDIT=250000
MAX_OUTPUT_TOKENS_PER_AUDIT=50000
```

Production secrets belong in a secret manager, not `.env` files. Commit only `.env.example` with placeholders.

## 17. Implementation Phases

### Phase 0: Contracts and evaluation first

- Define tenant, project, site, audit, finding, recommendation, approval, action, and evidence schemas.
- Create the initial gold dataset.
- Define model gateway and crawler interfaces.
- Decide hosted NIM region and review data-processing terms.
- Add OpenTelemetry correlation IDs from the first endpoint.

**Exit criteria**: API schemas, state machine, initial evaluation fixtures, and threat model are reviewed.

### Phase 1: Foundation

- Build Next.js shell and FastAPI gateway.
- Add OIDC login and tenant-scoped authorization.
- Add PostgreSQL migrations and audit event model.
- Add Redis and object-store abstractions.
- Add Docker Compose and GitHub Actions checks.

**Exit criteria**: an authenticated user can create a project and see durable state with tenant isolation tests.

### Phase 2: Website intelligence

- Implement allowlisted crawler with robots, sitemap, SSRF, byte, page, and time budgets.
- Store raw snapshots and normalized page versions.
- Implement deterministic SEO rules.
- Add finding evidence and deduplication.

**Exit criteria**: a fixture site produces reproducible findings without an LLM.

### Phase 3: Retrieval

- Enable pgvector.
- Implement section-aware chunking and content hashes.
- Integrate the selected embedding NIM.
- Add lexical/vector hybrid retrieval and tenant filters.
- Measure retrieval recall before adding a reranker.

**Exit criteria**: gold retrieval questions meet the target recall and deletion removes derived chunks and embeddings.

### Phase 4: NIM reasoning and agent graph

- Implement `NimClient` and model registry.
- Add structured outputs and Pydantic validation.
- Add LangGraph nodes and bounded tool loops.
- Add Temporal workflow and activities.
- Add cost, token, latency, and failure telemetry.

**Exit criteria**: an audit can gather evidence, produce a cited recommendation, and resume after a simulated worker restart.

### Phase 5: Approval and controlled execution

- Add recommendation review UI.
- Implement approval and rejection signals.
- Add deterministic action validation and idempotency.
- Build one CMS adapter in dry-run mode first.
- Add a separate executor worker and read-after-write verification.

**Exit criteria**: no test or simulated prompt injection can publish without a valid approval record.

### Phase 6: Production hardening

- Deploy managed containers and managed data services.
- Add backups, retention jobs, alerts, dashboards, and Sentry.
- Run load, failure-injection, SSRF, prompt-injection, and cross-tenant tests.
- Establish model/prompt promotion and rollback procedures.
- Run a staging audit against a controlled site.

**Exit criteria**: the system has an operational runbook, measurable SLOs, completed security review, and reproducible release process.

## 18. Explicit Non-Choices

These are deliberate decisions, not claims that the alternatives are bad:

- **No pure LLM context dump**: it wastes tokens and weakens evidence selection.
- **No vector-only retrieval**: exact SEO terms and URLs need lexical search.
- **No dedicated vector database initially**: pgvector avoids a second consistency and operations boundary.
- **No MongoDB as the primary store**: relational approvals and audit events benefit from constraints and transactions.
- **No Redis-only workflow state**: approvals and production actions must survive cache loss.
- **No unrestricted browser tool for the model**: browsing must be bounded, observable, and policy-controlled.
- **No unrestricted ReAct loop**: agent steps and tool permissions must be finite and testable.
- **No multi-agent swarm initially**: one evidence and approval policy is easier to audit and evaluate.
- **No direct model-to-CMS credentials**: the executor enforces approval and idempotency.
- **No Kubernetes before GPU self-hosting is needed**: managed containers reduce operational surface area.
- **No automatic cross-provider fallback**: changing where customer data is processed is a compliance decision.
- **No fine-tuning in the first release**: improve retrieval, rules, prompts, schemas, and evaluations first; fine-tune only when repeated, well-labeled failure patterns justify it.
- **No benchmark-only model selection**: promote models on website-growth evaluations, not generic scores.

## 19. Primary References

### NVIDIA NIM

- [NVIDIA NIM overview](https://docs.api.nvidia.com/nim/docs/introduction)
- [NIM LLM API reference](https://docs.nvidia.com/nim/large-language-models/latest/reference/api-reference.html)
- [NVIDIA API Catalog quickstart](https://docs.api.nvidia.com/nim/docs/api-quickstart)
- [NIM tool calling and MCP integration](https://docs.nvidia.com/nim/large-language-models/latest/advanced-use-cases/tool-calling-and-mcp.html)
- [NIM structured generation](https://docs.nvidia.com/nim/large-language-models/1.12.0/structured-generation.html)
- [NIM model catalog](https://build.nvidia.com/models)
- [Llama 3.3 70B NIM model card](https://build.nvidia.com/meta/llama-3_3-70b-instruct)
- [NeMo Retriever embedding support matrix](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/support-matrix.html)

### Application and data infrastructure

- [Next.js documentation](https://nextjs.org/docs)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [pgvector repository and indexing guidance](https://github.com/pgvector/pgvector)
- [Temporal durable approval workflows](https://docs.temporal.io/guides/reliable-document-approvals)
- [LangGraph interrupts and human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts)

### Observability and security

- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)
- [Langfuse observability](https://langfuse.com/docs/observability/overview)
- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [RFC 9309 robots exclusion protocol](https://www.rfc-editor.org/rfc/rfc9309)
- [GitHub Actions OIDC](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-cloud-providers)

## 20. Portfolio Demo

The smallest convincing demonstration should show the entire safety and evidence loop:

1. Add a website and business goal.
2. Run a bounded audit.
3. Show deterministic findings with page and heading evidence.
4. Ask the agent to prioritize issues against the stated goal.
5. Generate a cited content brief.
6. Propose one safe metadata change.
7. Validate and request approval.
8. Approve it and execute through a dry-run CMS adapter.
9. Display the workflow, approval, action, and verification audit trail.

The demo is successful when a developer can see not only what the model recommended, but which evidence supported it, which rules constrained it, who approved it, what was executed, and how the outcome will be measured.
