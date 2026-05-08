# TicketPilot

An AI-powered support ticket resolution system demonstrating **multi-agent orchestration**, **RAG**, and **observable AI infrastructure**.

## Overview

TicketPilot automates the lifecycle of support tickets—from ingestion to resolution—using a **multi-agent pipeline**: a Router agent classifies the ticket, a Context agent retrieves relevant knowledge, a Resolver agent generates a response, and a Quality agent validates the result. The entire pipeline is orchestrated end-to-end.

Built as a portfolio project for an AI Engineer role at a hosting company.

## Key Features

- **Multi-Agent Pipeline** — Router → Context → Resolver → Quality agents with streaming state
- **REST API** — FastAPI with ticket CRUD, document ingestion, and search endpoints
- **RAG Knowledge Base** — Qdrant vector store with OpenRouter embeddings
- **Cost Optimization** — Smart model selection (cheap triage vs. powerful resolver), token tracking
- **Prometheus Metrics** — Token usage, latency, ticket counts, and resolution rates
- **Frontend Dashboard** — Submit tickets, check status, search knowledge base, auto-refresh
- **Event-Driven** — Redis message queue for async worker processing
- **Containerized** — Full Docker Compose stack (PostgreSQL, Redis, Qdrant, FastAPI, Worker, Prometheus)

## Architecture

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Frontend   │────▶│   REST API     │────▶│   Redis Queue  │
│ (HTML/JS)   │     │   (FastAPI)    │     │   (event bus)  │
└─────────────┘     └────────────────┘     └────────┬────────┘
                                                    │
                                                    ▼
┌──────────────────────────────────────────────────────────┐
│                   Orchestrator Pipeline                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐   │
│  │ Router  │──│ Context │──│Resolver │──│  Quality  │   │
│  │  Agent  │  │  Agent  │  │  Agent  │  │   Agent   │   │
│  └─────────┘  └─────────┘  └─────────┘  └───────────┘   │
│     classify     RAG          respond      validate      │
└──────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Knowledge    │◀───│  Vector Store  │◀───│  OpenRouter     │
│  Base (docs)  │     │  (Qdrant)      │     │  Embeddings     │
└────────────────┘     └────────────────┘     └─────────────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Ticket       │◀───│  Resolution    │     │  Prometheus     │
│  Resolved     │     │  / Escalation │     │  Metrics        │
└────────────────┘     └────────────────┘     └─────────────────┘
```

## Multi-Agent System

| Agent | Role | Model |
|-------|------|-------|
| **Router Agent** | Classifies ticket (access/billing/technical/account) and sets priority | Cheap (gemini-flash) |
| **Context Agent** | Retrieves relevant documents from Qdrant vector store | No LLM (RAG only) |
| **Resolver Agent** | Generates resolution using ticket context + knowledge base | Powerful (claude-sonnet) |
| **Quality Agent** | Validates resolution quality, decides: resolved or escalated | Cheap |
| **Orchestrator** | Coordinates the pipeline, updates database, tracks metrics | Logic only |

## Tech Stack

| Component | Technology |
|------------|------------|
| API | FastAPI |
| Agent Framework | Custom multi-agent (LangChain for LLM calls) |
| LLM Provider | OpenRouter (Gemini Flash, Claude Sonnet) |
| Embeddings | OpenRouter API (`text-embedding-3-small`, 384 dims) |
| Vector Database | Qdrant |
| Message Queue | Redis |
| Database | PostgreSQL (SQLAlchemy) |
| Monitoring | Prometheus |
| Containerization | Docker, Docker Compose |
| Frontend | Vanilla HTML / CSS / JS |
| Language | Python 3.11+ |

## Project Structure

```
ticketpilot/
├── app/
│   ├── agents/               # Multi-agent system
│   │   ├── base.py           # BaseAgent abstract class
│   │   ├── orchestrator.py   # Pipeline coordinator
│   │   ├── router_agent.py   # Ticket classifier
│   │   ├── context_agent.py  # RAG context retriever
│   │   ├── resolver_agent.py # Resolution generator
│   │   └── quality_agent.py  # Quality validator
│   ├── api/
│   │   └── routes.py         # FastAPI endpoints
│   ├── rag/
│   │   ├── vector_store.py   # Qdrant integration
│   │   ├── embedding.py      # OpenRouter embeddings
│   │   └── document_processor.py  # Text chunking & ingestion
│   ├── workers/
│   │   ├── __init__.py
│   │   └── worker.py         # Redis consumer, delegates to Orchestrator
│   ├── models.py             # SQLAlchemy models
│   ├── database.py           # Database session
│   ├── metrics.py            # Prometheus metrics
│   └── main.py               # FastAPI app initialization
├── frontend/
│   ├── index.html            # Dashboard
│   ├── styles.css            # Modern SaaS design
│   └── app.js                # API calls + auto-refresh
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── prometheus.yml
├── requirements.txt
├── .env.example
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

3. Edit `.env` and set your OpenRouter API key and preferred models:
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

### Usage

Open the **frontend dashboard** at **[http://localhost:8000](http://localhost:8000)**.

#### From the Dashboard:
1. **Ingest Knowledge Base** — Click the button to load sample support docs
2. **Create Ticket** — Describe your issue and click Submit
3. **Watch Processing** — Ticket list auto-refreshes every 5 seconds
4. **Check Status** — Enter a ticket ID to see detailed status
5. **Search KB** — Query the knowledge base for relevant articles
6. **Metrics** — View Prometheus token/latency tracking

#### From the Terminal:
```bash
# Create a ticket
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"description": "I cannot log in to my account"}'

# Check status
curl http://localhost:8000/api/v1/tickets/1

# List all tickets
curl http://localhost:8000/api/v1/tickets

# Search knowledge base
curl "http://localhost:8000/api/v1/documents/search?query=login&limit=3"
```

#### Monitoring:
- **Prometheus Metrics**: http://localhost:8000/api/v1/metrics
- **Prometheus UI**: http://localhost:9090

## Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | Your OpenRouter API key (required) |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector DB URL |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `TRIAGE_MODEL` | `google/gemini-2.0-flash-001` | Cheap model for classification |
| `POWER_MODEL` | `anthropic/claude-sonnet-4-20250514` | Powerful model for resolution |

## Roadmap

- [x] Project setup and Docker stack
- [x] PostgreSQL persistence (SQLAlchemy)
- [x] REST API (tickets, documents, metrics)
- [x] Redis event-driven worker
- [x] Multi-agent pipeline (Router → Context → Resolver → Quality)
- [x] RAG knowledge base (Qdrant + OpenRouter embeddings)
- [x] Prometheus monitoring (token usage, latency, ticket counts)
- [x] Cost optimization (model selection, token tracking)
- [x] Frontend dashboard with auto-refresh
- [x] Unit & integration tests (20 pytest tests)
- [x] SSE real-time updates (EventSource)
- [x] Escalation workflow with human-in-the-loop (`/admin` page)
- [x] Admin page with Markdown-formatted resolutions

> **All roadmap items completed!** 🎉

## License

MIT

## Author

Built for AI Engineer portfolio demonstration.
