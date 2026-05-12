Now I have read every specified file. Here is the structured summary.

---

# Code Context — TicketPilot

## 1. Entry Points & Structure

### `app/main.py` (lines 1-43)
- Creates FastAPI app, mounts static files (`/static` → `frontend/`), serves `index.html` at `/` and `admin.html` at `/admin`.
- Calls `Base.metadata.create_all(bind=engine)` at import time — **side-effect at module load**.
- Adds `RateLimitMiddleware` then `CORSMiddleware` (order matters; CORS runs second).
- Imports `Ticket` model purely to trigger its registration with `Base`.

### `app/api/routes.py` (lines 1-160)
- `APIRouter(prefix="/api/v1")` with all endpoints.
- Pydantic models `TicketCreate`, `TicketResponse`, `TicketResolve` defined inline.
- **Implicit coupling**: `redis_client` created as module-level singleton. Tests patch `redis.from_url` via `mock_redis` fixture.
- SSE endpoint (`/tickets/stream`) runs a `SessionLocal()` directly (bypassing dependency injection) — **two DB session patterns coexist**.
- Document endpoints (`/documents`, `/knowledge-base/ingest`, `/documents/search`) instantiate `DocumentProcessor`/`VectorStore` inline — no dependency injection.

### `app/workers/worker.py` (lines 1-35)
- Infinite `while True` loop with `brpop("ticket_queue", timeout=5)`.
- Creates a single `Orchestrator` instance at module level.
- No health-check endpoint, no graceful shutdown handling, no backpressure.
- **Constraint**: If `process_ticket` raises, the worker sleeps 5s and continues — no dead-letter queue.

---

## 2. Agent Pipeline Mechanics

### `app/agents/base.py` (lines 1-55)
- `BaseAgent.__init__(model=None, temperature=0.3)` — defaults model to `TRIAGE_MODEL` env var.
- `llm` property == **lazy singleton** via `ChatOpenAI` talking to OpenRouter.
- `run(state: dict) -> dict` — abstract. All agents mutate and return the **same state dict**.
- `track_tokens(response, model_name)` — fragile: checks `hasattr(response, 'usage_metadata')`; LangChain response shapes vary by model.

### `app/agents/orchestrator.py` (lines 1-125)
- `Orchestrator.__init__()` — instantiates all four sub-agents directly. **Hardcoded pipeline order**: Router → Context → Resolver → Quality.
- `process_ticket(ticket_id, description) -> str` — creates a fresh `state` dict, runs each agent, then calls `_update_ticket()`.
- **Quality gate**: if `quality_check.passed` → resolved; else escalated. Uses thresholds (confidence >= 0.6).
- `_update_ticket()` — opens own DB session, writes resolution, status, escalation_info (JSON-serialized). Publishes to Redis Pub/Sub.
- Redis Pub/Sub helper `_publish_ticket_event` — module-level lazy singleton `_redis_pub`.

### `app/agents/router_agent.py` (lines 1-56)
- `RouterAgent.run(state)` — constructs a prompt, calls LLM, parses JSON output.
- Fields: `category`, `priority`, `requires_rag`, `reason`.
- **Fallback**: on any exception, defaults to `general`/`medium`/`True`. No retry.

### `app/agents/context_agent.py` (lines 1-35)
- `ContextAgent.run(state)` — calls `VectorStore.search(description, limit=3)`. Stores `context_docs` as list of `{doc_id, text, score}`.
- **Constraint**: only uses `state["description"]` as query — no fusion with category or priority.

### `app/agents/resolver_agent.py` (lines 1-45)
- Uses `POWER_MODEL` env var (not `TRIAGE_MODEL`) with higher temperature (0.7).
- Builds context text from `context_docs` (truncated to 300 chars each).
- No structured output — returns raw free-text resolution.

### `app/agents/quality_agent.py` (lines 1-145)
- Three-part check: citation matching (term overlap), hallucination rules (regex for $amounts, tools), LLM quality assessment.
- `_calculate_confidence()` — weighted formula: citation (30%), hallucination penalty, LLM risk (20%).
- **Threshold**: `passed = confidence >= 0.6 and not critical_issues`.
- `_extract_key_terms()` — regex-based extraction of capitalized terms and quoted strings.
- **Brittle patterns**: regex-based hallucination detection is fragile; LLM quality check re-parses JSON from model output (same fallback pattern as RouterAgent).

---

## 3. Data Layer

### `app/database.py` (lines 1-15)
- SQLAlchemy with PostgreSQL (`DATABASE_URL` env var). Defaults to `postgresql://ticketpilot:ticketpilot@db:5432/ticketpilot`.
- `get_db()` — standard generator dependency for FastAPI.

### `app/models.py` (lines 1-51)
- `TicketStatus` enum: `OPEN`, `IN_PROGRESS`, `RESOLVED`, `ESCALATED`.
- `Ticket` model: `escalation_info` stored as JSON text column, deserialized in `to_dict()`.
- `resolved_by` — stores `"agent"` or `"admin"` (magic strings).
- `to_dict()` — manually maps fields; **no `updated_at` in output if not set** (returns None).

### `app/rag/vector_store.py` (lines 1-68)
- Wraps Qdrant client. Collection: `ticketpilot_knowledge`, vector size 384, COSINE distance.
- `add_document()` — hashes `doc_id` with MD5 to get integer ID (`abs(hashlib.md5(...) % (2**31))` — **collision risk**).
- `search()` — returns up to `limit` results with `doc_id`, `text`, `score`.

### `app/rag/embedding.py` (lines 1-27)
- `@lru_cache(maxsize=256)` on `get_embedding(text)` — caches embedding results (cache key is raw text; long texts won't repeat).
- Calls OpenRouter `/api/v1/embeddings` with `openai/text-embedding-3-small`, dimensions=384.
- **No retry logic** — raises on failure, which cascades to agents.

### `app/rag/document_processor.py` (lines 1-59)
- `process_text()` — chunks by `CHUNK_SIZE`/`CHUNK_OVERLAP` (env vars, defaults 1000/200).
- `ingest_sample_knowledge_base()` — hardcoded 3 sample docs about login, billing, performance.
- **Chunking is naive**: splits by character count with no sentence/paragraph awareness.

---

## 4. Frontend

### `frontend/index.html` (inline Alpine.js app)
- Tailwind CSS + Alpine.js + marked + DOMPurify (all CDN).
- `app()` function: SSE connection falls back to polling (5s interval). Stat counters computed client-side from ticket list.
- Create ticket, ingest KB, search KB, live ticket list with status badges.
- **Escalated tickets** show a "Resolve" button linking to `/admin`.

### `frontend/admin.html` (separate Alpine.js app)
- Polls `/api/v1/tickets?status=escalated` every 10s.
- Shows escalation info metadata badges. Allows admin to write and submit resolution via PATCH `/api/v1/tickets/{id}/resolve`.
- Collapsible AI resolution for reference.

### `frontend/app.js` (legacy Vanilla JS — referenced by tests)
- Same functionality as Alpine.js version but in Vanilla JS. Used by tests that check `/static/app.js`.
- Both implementations exist — **duplicated logic** (SSE, polling, ticket rendering).

### `frontend/styles.css`
- Referenced in tests (`test_css_exists`) but contains basic styling.

---

## 5. Tests

### `tests/conftest.py` (lines 1-80)
- Forces `DATABASE_URL=sqlite:///./test.db` before importing app modules.
- **Creates a second engine** (`TestSessionLocal`) instead of reusing app's `SessionLocal` — this works because `override_get_db` is used.
- `mock_redis` — patches `app.api.routes.redis.from_url` and `redis_client`.
- `mock_llm` — patches `BaseAgent.llm` as a `PropertyMock`. Yields a callable that sets `mock_instance.invoke.return_value`. **Fragile**: the lambda mutates `mock_instance.__dict__` directly.
- `mock_qdrant` — patches `VectorStore.search` and stubs `QdrantClient`.
- `setup_database` — autouse fixture drops and recreates tables for every test.

### `tests/test_api.py` (lines 1-102)
- Tests: health, root HTML, CRUD, list ordering (desc), empty description, missing field, param inputs, empty list, knowledge base ingest, metrics.
- **Coverage gaps**: no test for SSE stream, no test for PATCH resolve, no test for document search, no test for rate limiting, no test for error responses from worker.

### `tests/test_agents.py` (lines 1-68)
- Tests RouterAgent (classification, bad JSON fallback), ContextAgent (retrieval, empty results), QualityAgent (empty/error resolution, with context, LLM fallback).
- **Coverage gaps**: no test for ResolverAgent, no test for Orchestrator integration, no test for `requires_rag=False` branch, no test for escalation path, no test for token tracking.

---

## 6. Quality / Evaluation

### `evaluation/run_evals.py` (lines 1-115)
- Runs full integration eval: ingests KB, creates tickets via API, polls for resolution, calls `evaluate_single()`.
- Hardcoded `API_BASE = "http://localhost:8000/api/v1"`.
- `wait_for_processing()` — polls every 5s up to 300s total.
- **Exits non-zero** if `avg_keyword_coverage < 0.5`.

### `evaluation/metrics.py` (lines 1-88)
- `keyword_coverage()` — substring matching against expected keywords.
- `exact_match()` — 30% sentence overlap threshold (arbitrary).
- `retrieval_hitrate()` — keyword presence in concatenated context docs.
- `rouge_l_similarity()` — word-level LCS F1.
- `evaluate_single()` — runs all metrics.
- `summarize_results()` — averages across valid results.

### `evaluation/results.json`
- 3 tickets evaluated, all escalated (not resolved). Avg keyword coverage 66.7%, ROUGE-L F1 ~0.04, exact match rate 0%.
- **All tickets escalated** — suggests quality gate confidence < 0.6.

### `evaluation/gold_dataset.jsonl`
- 25 labeled tickets (categories: access, billing, technical, account), each with expected keywords and resolution.

---

## 7. Infra & Configuration

### `docker-compose.yml`
- Services: db (PostgreSQL 16), redis (7), qdrant (latest), api, worker, prometheus.
- API port 8000, Redis 6379, Qdrant 6333, Prometheus 9090.
- API and worker mount `./app:/app/app` as volumes (live code reload in development).
- **No depends_on health checks** — services may start before dependencies are ready.

### `Dockerfile.api` / `Dockerfile.worker`
- Both based on `python:3.11-slim`, install requirements, copy app code.
- API: `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- Worker: `CMD ["python", "-m", "app.workers.worker"]`

### `requirements.txt`
- Pinned versions. Key: `langchain==0.0.340` (old), `openai==1.3.0`, `qdrant-client==1.6.0`.

### `.env.example`
- Documents all env vars: `OPENROUTER_API_KEY`, `QDRANT_URL`, `REDIS_URL`, `DATABASE_URL`, `LOG_LEVEL`, `TRIAGE_MODEL`, `POWER_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`.

### `.github/workflows/test.yml`
- Runs on push to any branch or PR to main. Installs system deps, pip installs requirements + pytest, runs `pytest tests/ -v --tb=long`.
- **No services (Redis, Qdrant, Postgres) in CI** — tests use SQLite + mocks, which is fine.

### `.github/workflows/docker.yml`
- On push to main, builds and pushes API and Worker images to GHCR.

### `prometheus.yml`
- Scrapes `api:8000/api/v1/metrics` every 15s.

---

## 8. Middleware

### `app/middleware/rate_limit.py` (lines 1-87)
- `RateLimitMiddleware` extends `BaseHTTPMiddleware`.
- Redis-backed sliding window via sorted sets. Falls back silently if Redis unavailable.
- Hardcoded `RATE_LIMITS` dict (POST /tickets: 10/min, POST /knowledge-base/ingest: 5/min, GET /search: 30/min, GET /stream: 10/min, PATCH /resolve: 20/min).
- Uses `path.startswith(route)` for matching — **catch-all for sub-paths but could over-match**.
- Sets `X-RateLimit-*` headers on response.

---

## 9. Metrics

### `app/metrics.py` (lines 1-36)
- Prometheus counters: `ticket_created_total`, `ticket_resolved_total`, `ticket_escalated_total`, `token_usage_total` (with `model` label), `worker_tickets_processed_total`.
- Histogram: `ticket_processing_seconds` (buckets: 0.1–60s).
- `http_request_duration_seconds` — **declared but never instrumented** (no middleware hooks it up).
- `metrics_endpoint()` — returns Prometheus text format.

---

## Cross-Cutting Constraints & Risks

| Risk | Details |
|------|---------|
| **Adding a new agent** | Must modify `Orchestrator.__init__`, `process_ticket`, `state` dict shape, `_update_ticket` — no plugin system |
| **Changing agent order** | Hardcoded in `process_ticket`. Quality gate enforces Router→Context→Resolver→Quality |
| **Modifying Ticket model** | Must update `to_dict()`, `TicketStatus` enum, `_update_ticket`, frontend status badges |
| **New LLM model** | Only two model slots (TRIAGE_MODEL, POWER_MODEL). Router/Context/Quality share TRIAGE_MODEL; Resolver uses POWER_MODEL |
| **Redis outage** | Rate limiter and SSE silently skip/fail. Worker `brpop` blocks indefinitely |
| **Qdrant outage** | ContextAgent catches exception and returns empty docs. VectorStore init failure is logged but swallowed |
| **State dict coupling** | Every agent reads/writes the same dict with string keys — no validation, no typing |
| **Hardcoded magic strings** | `TRIAGE_MODEL`, `POWER_MODEL`, categories (`access`, `billing`, ...), `resolved_by` values (`"agent"`, `"admin"`), collection name `"ticketpilot_knowledge"`, vector dimension `384` |
| **Thread safety** | `BaseAgent._llm` lazy init is not thread-safe; Redis pubsub helper has race on `_redis_pub = None` check |
| **Test isolation** | `conftest.py` uses file-based SQLite (`test.db`) — parallel test runs collide. Mock fixtures leak between tests if not reset |

---

## Clarification Questions

1. **Pipeline flexibility**: Is the 4-agent pipeline (Router → Context → Resolver → Quality) intended to be the final architecture, or is there a plan for dynamic agent routing, parallel agents, or a plugin system for adding new agents?

2. **Quality gate calibration**: All 3 evaluated tickets were escalated (confidence < 0.6). Is 0.6 the intended threshold, or should it be tuned? Should escalation produce a different user experience (e.g., notify admin) beyond just the `/admin` polling?

3. **State dict governance**: The shared `state` dict has no schema validation. Would introducing a typed `PipelineState` dataclass/Pydantic model be acceptable, or is the dict pattern deliberately kept flexible?

4. **`http_request_duration_seconds` metric**: Declared but never populated. Is there a plan to wire it up (e.g., via middleware), or should it be removed?

5. **Frontend maintenance**: Both `app.js` (Vanilla JS) and `index.html` (Alpine.js) implement the same UI. Is the Vanilla JS version (`app.js`) considered legacy and slated for removal, or do both need to be kept in sync?