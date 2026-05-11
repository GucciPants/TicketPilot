# TicketPilot

An AI-powered support ticket resolution system demonstrating **multi-agent orchestration**, **RAG**, **evaluation-driven quality**, and **observable AI infrastructure**.

## Overview

TicketPilot automates the lifecycle of support tickets using a **multi-agent pipeline**: Router → Context → Resolver → Quality. Each agent has a specific role, from classification to hallucination detection. The entire system runs in Docker, uses Redis for event-driven processing, and features real-time updates via SSE with Redis Pub/Sub.

Built as an AI Engineer portfolio demonstration project.

## Key Features

### Multi-Agent Pipeline
| Agent | Role | Model |
|---|---|---|
| **Router Agent** | Classifies ticket (access/billing/technical/account), sets priority | Cheap model |
| **Context Agent** | Retrieves relevant documents from Qdrant vector store | RAG only (no LLM) |
| **Resolver Agent** | Generates resolution using context + knowledge base | Powerful model |
| **Quality Agent** | Validates with **hallucination detection**, **citation check**, **confidence scoring** | Cheap model |
| **Orchestrator** | Coordinates pipeline, publishes Redis Pub/Sub events, tracks metrics | Logic only |

### Quality Assurance
- **Hallucination detection** — regex-based checks for unsupported claims (amounts, tools)
- **Citation check** — verifies resolution key terms appear in RAG context
- **Confidence scoring** — combines citation (30%), hallucination (50%), and LLM assessment (20%) into 0.0-1.0 score
- **Fail-closed** — on uncertainty, ticket is escalated for human review

### Infrastructure
- **True SSE via Redis Pub/Sub** — worker publishes events, frontend receives zero-latency updates
- **Rate limiting** — Redis-based, 10 POST/min for tickets, 30 GET/min for search
- **Embedding LRU cache** — `@lru_cache(maxsize=256)` avoids duplicate OpenRouter API calls
- **Prometheus metrics** — token usage, latency, ticket counts, resolution rates
- **Eval framework** — 25 gold-standard tickets, ROUGE-L, keyword coverage, retrieval hitrate

## Architecture

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Frontend   │────▶│   REST API     │────▶│   Redis Queue  │
│ (Tailwind+  │     │   (FastAPI)    │     │   (event bus)  │
│  Alpine.js) │◀────│  + SSE Stream  │◀────│  Redis Pub/Sub │
└─────────────┘     └────────────────┘     └────────┬────────┘
                                                    │
                                                    ▼
┌──────────────────────────────────────────────────────────┐
│                   Orchestrator Pipeline                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐   │
│  │ Router  │──│ Context │──│Resolver │──│  Quality  │   │
│  │  Agent  │  │  Agent  │  │  Agent  │  │   Agent   │   │
│  └─────────┘  └─────────┘  └─────────┘  └───────────┘   │
│     classify     RAG          respond    validate +       │
│                                           hallucination   │
│                                           detection       │
└──────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Knowledge    │◀───│  Vector Store  │◀───│  OpenRouter     │
│  Base (docs)  │     │  (Qdrant)      │     │  Embeddings     │
│  (configurable│     │                │     │  (LRU cached)   │
│   chunking)   │     │                │     │                 │
└────────────────┘     └────────────────┘     └─────────────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Ticket       │◀───│  Resolution    │     │  Prometheus     │
│  Resolved     │     │  / Escalation │     │  + Rate Limit   │
│  (rate limited)│     │                │     │  + Metrics       │
└────────────────┘     └────────────────┘     └─────────────────┘
```

## Tech Stack

| Component | Technology |
|------------|------------|
| API | FastAPI |
| Agent Framework | Custom multi-agent (LangChain for LLM calls) |
| LLM Provider | OpenRouter (configurable models) |
| Embeddings | OpenRouter API (`text-embedding-3-small`, 384 dims, LRU cached) |
| Vector Database | Qdrant |
| Message Queue | Redis (also used for rate limiting + Pub/Sub) |
| Database | PostgreSQL (SQLAlchemy) |
| Monitoring | Prometheus |
| Rate Limiting | Redis-based middleware |
| Frontend | Alpine.js + Tailwind CSS (CDN) |
| Evaluation | 25 gold tickets, ROUGE-L, keyword coverage |
| Containerization | Docker, Docker Compose |
| Language | Python 3.11+ |

## Project Structure

```
ticketpilot/
├── app/
│   ├── agents/               # Multi-agent system
│   │   ├── base.py           # BaseAgent with lazy LLM + token tracking
│   │   ├── orchestrator.py   # Pipeline coordinator + Redis Pub/Sub publisher
│   │   ├── router_agent.py   # Ticket classifier
│   │   ├── context_agent.py  # RAG context retriever
│   │   ├── resolver_agent.py # Resolution generator (POWER_MODEL)
│   │   └── quality_agent.py  # Hallucination detection + citation check + confidence
│   ├── api/
│   │   └── routes.py         # FastAPI endpoints + SSE stream
│   ├── middleware/
│   │   └── rate_limit.py     # Redis-based rate limiting middleware
│   ├── rag/
│   │   ├── vector_store.py   # Qdrant integration
│   │   ├── embedding.py      # OpenRouter embeddings (LRU cached)
│   │   └── document_processor.py  # Configurable chunking ingestion
│   ├── workers/
│   │   ├── __init__.py
│   │   └── worker.py         # Redis consumer → Orchestrator
│   ├── models.py             # SQLAlchemy models (with escalation_info)
│   ├── database.py           # Database session
│   ├── metrics.py            # Prometheus metrics
│   └── main.py               # FastAPI app + CORS + logging
├── evaluation/               # Eval framework
│   ├── gold_dataset.jsonl    # 25 gold-standard tickets
│   ├── metrics.py            # ROUGE-L, keyword coverage, retrieval hitrate
│   └── run_evals.py          # Automated evaluation script
├── frontend/
│   ├── index.html            # Dashboard (Alpine.js + Tailwind)
│   └── admin.html            # Admin page (Alpine.js + Tailwind)
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── prometheus.yml
├── requirements.txt
├── .env.example
├── .dockerignore
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Git
- OpenRouter API key ([get one free](https://openrouter.ai/keys))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/GucciPants/TicketPilot.git
   cd TicketPilot
   ```

2. Create `.env` file from example:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your API key and preferred models:
   ```env
   OPENROUTER_API_KEY=sk-or-v1-your_actual_key
   TRIAGE_MODEL=google/gemini-2.0-flash-001
   POWER_MODEL=anthropic/claude-sonnet-4-20250514
   ```

4. Start all services:
   ```bash
   docker-compose up -d
   ```

5. Ingest the sample knowledge base:
   ```bash
   curl -X POST http://localhost:8000/api/v1/knowledge-base/ingest
   ```

## Usage

### Dashboard
Open **[http://localhost:8000](http://localhost:8000)**:
- **Create Ticket** — describe an issue and submit
- **Live Updates** — ticket list updates instantly via SSE
- **Stat Cards** — total / resolved / escalated counts
- **Knowledge Base** — ingest sample docs and search

### Admin Console
Open **[http://localhost:8000/admin](http://localhost:8000)**:
- View escalated tickets with AI-generated resolutions
- Review quality check data (confidence, citation score, hallucination warnings)
- Manually resolve tickets (human-in-the-loop)

### API
```bash
# Create a ticket
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"description": "I cannot log in to my account"}'

# Check status (includes escalation_info with quality data)
curl http://localhost:8000/api/v1/tickets/1

# List all tickets (supports ?status=escalated filter)
curl http://localhost:8000/api/v1/tickets

# Manually resolve an escalated ticket
curl -X PATCH http://localhost:8000/api/v1/tickets/1/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution": "Issue fixed by admin."}'

# Interactive API docs
http://localhost:8000/docs
```

### Monitoring
- **Prometheus Metrics**: http://localhost:8000/api/v1/metrics
- **Prometheus UI**: http://localhost:9090

## Evaluation

Run the automated evaluation against 25 gold-standard tickets:

```bash
pip install -r requirements.txt
python -m evaluation.run_evals --verbose
```

Metrics measured:
| Metric | Description |
|---|---|
| **Keyword coverage** | % of expected keywords found in AI response |
| **ROUGE-L F1** | Longest common subsequence similarity |
| **Retrieval hitrate** | % of relevant KB documents found by RAG |
| **Exact match rate** | Sentence-level overlap with gold standard |

Options:
```bash
python -m evaluation.run_evals --tickets 10 --output results.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | OpenRouter API key **(required)** |
| `TRIAGE_MODEL` | `google/gemini-2.0-flash-001` | Model for routing + quality check |
| `POWER_MODEL` | `anthropic/claude-sonnet-4-20250514` | Model for resolution generation |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector DB URL |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING) |
| `CHUNK_SIZE` | `1000` | Document chunk size for RAG |
| `CHUNK_OVERLAP` | `200` | Chunk overlap for RAG |

## Rate Limits

| Endpoint | Method | Limit |
|---|---|---|
| `/api/v1/tickets` | POST | 10 requests/minute |
| `/api/v1/knowledge-base/ingest` | POST | 5 requests/minute |
| `/api/v1/documents/search` | GET | 30 requests/minute |
| `/api/v1/tickets/stream` | GET | 10 connections/minute |
| Default (other) | — | 60 requests/minute |

Rate limit headers are included in every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

## Quality Check

The Quality Agent evaluates every resolution before it's finalized:

1. **Citation check** — extracts key terms from the resolution and verifies they appear in RAG context
2. **Hallucination detection** — regex checks for unsupported dollar amounts, tool names, and suspicious length
3. **LLM assessment** — final quality pass with hallucination risk scoring
4. **Combined confidence** — `0.0-1.0` score: citation (30%) + hallucination (50%) + LLM (20%)
5. **Decision** — confidence ≥ 0.6 with no critical issues → resolved, else → escalated

Quality data is stored in `tickets.escalation_info` and visible on the admin page.

## CI/CD

GitHub Actions automatically runs on every push:

| Workflow | Trigger | Action |
|---|---|---|
| **Tests** | Every push + PR to main | Runs 29 pytest tests (API + agents) |
| **Docker Build** | Push to main | Builds and pushes `ticketpilot-api` and `ticketpilot-worker` images to GitHub Container Registry |

### Running Tests

The test suite uses `pytest` with mock fixtures, no external services needed:
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

**Test structure:** 29 tests total:
- **20 API tests** — health, tickets CRUD, knowledge base, metrics, frontend
- **9 Agent tests** — Router classification, Context retrieval, Quality validation

All external dependencies (LLM, Redis, Qdrant, PostgreSQL) are mocked.

## Roadmap

- [x] Project setup and Docker stack
- [x] PostgreSQL persistence (SQLAlchemy)
- [x] REST API (tickets, documents, metrics)
- [x] Redis event-driven worker
- [x] Multi-agent pipeline (Router → Context → Resolver → Quality)
- [x] Quality Agent (hallucination detection, citation check, confidence)
- [x] RAG knowledge base (Qdrant + configurable chunking + LRU cached embeddings)
- [x] Prometheus monitoring (token usage, latency, ticket counts)
- [x] Cost optimization (model selection, token tracking)
- [x] Rate limiting (Redis-based middleware)
- [x] Frontend dashboard (Tailwind + Alpine.js)
- [x] True SSE with Redis Pub/Sub (zero-latency updates)
- [x] Escalation workflow with human-in-the-loop (`/admin` page)
- [x] Unit & integration tests (29 pytest tests: 20 API + 9 agent)
- [x] Evaluation framework (25 gold tickets, ROUGE-L, keyword coverage)
- [x] CI/CD with GitHub Actions (tests + Docker build)
- [x] Consistent logging across all modules

> **All roadmap items completed!** 🎉

## License

MIT

## Author

Built for AI Engineer portfolio demonstration.
