# TicketPilot

An AI-powered support ticket resolution system demonstrating agentic workflows, RAG, and orchestration for modern customer service automation.

## Overview

TicketPilot is a showcase project for building an AI-driven ticketing backbone. It automates the lifecycle of support tickets—from ingestion to resolution—using intelligent agents, retrieval-augmented generation (RAG), and hybrid orchestration (low-code + code-first). The system is designed to be modular, observable, and cost-efficient.

## Key Features

- **REST API** for ticket ingestion and status polling (FastAPI)
- **AI Agent** for ticket triage, context retrieval, and resolution (Claude/GPT via OpenRouter)
- **RAG Pipeline** over internal knowledge base (Qdrant vector store)
- **Hybrid Orchestration**: n8n for low-code workflows, with option for Airflow/Dagster
- **Cost & Latency Monitoring** (Prometheus, custom metrics)
- **Event-driven architecture** with Redis message queue
- **Containerized** with Docker Compose for easy local setup

## Architecture

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Ticket     │────▶│   REST API     │────▶│   Redis Queue  │
│  Source     │     │   (FastAPI)    │     │   (event bus)  │
└─────────────┘     └────────────────┘     └────────┬────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  n8n Workflow │◀───│  Ticket        │────▶│  Agent Worker  │
│  (low-code)   │     │  Created       │     │  (LLM + RAG)   │
└────────────────┘     └────────────────┘     └────────┬────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Knowledge    │◀───│  Vector Store  │◀───│  Embedding     │
│  Base (docs)  │     │  (Qdrant)      │     │  Service       │
└────────────────┘     └────────────────┘     └─────────────────┘
                                                    │
                                                    ▼
┌────────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Ticket       │◀───│  Resolution    │     │  Prometheus     │
│  Resolved     │     │  / Escalation │     │  Metrics        │
└────────────────┘     └────────────────┘     └─────────────────┘
```

## Tech Stack

| Component | Technology |
|------------|------------|
| API | FastAPI |
| Agent Framework | LangChain (optional) or custom agents |
| LLM | OpenRouter (Claude, GPT, Gemini) |
| Vector Database | Qdrant |
| Embeddings | sentence-transformers or OpenRouter embeddings |
| Orchestration | n8n (low-code), optionally Airflow |
| Message Queue | Redis |
| Monitoring | Prometheus |
| Containerization | Docker, Docker Compose |
| Language | Python 3.11+ |

## Project Structure

```
ticketpilot/
├── app/
│   ├── api/              # FastAPI routes
│   ├── agents/           # AI agent logic
│   ├── rag/              # RAG pipeline (embedding, vector store)
│   ├── services/         # Redis, Qdrant, LLM clients
│   ├── workers/          # Background workers (consume from Redis)
│   └── main.py
├── n8n/                  # n8n workflow definitions (JSON)
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── requirements.txt
├── .env.example
└── README.md
```

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Git
- Python 3.11+ (for local development)
- OpenRouter API key (get it from openrouter.ai)

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

3. Edit `.env` and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your_key_here
   ```

4. Start all services with Docker Compose:
   ```bash
   docker-compose up -d
   ```
   This will start:
   - **PostgreSQL** (port 5432)
   - **Redis** (ports 6379)
   - **Qdrant** (port 6333)
   - **FastAPI** (port 8000)
   - **Worker** (background process)
   - **Prometheus** (port 9090)

5. Wait for services to start, then ingest sample knowledge base:
   ```bash
   curl -X POST http://localhost:8000/api/v1/knowledge-base/ingest
   ```

### Usage

#### Create a support ticket:
```bash
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"description": "I cannot log in to my account"}'
```

Response will include ticket ID. Worker will process it automatically.

#### Check ticket status:
```bash
curl http://localhost:8000/api/v1/tickets/{ticket_id}
```

#### Search knowledge base:
```bash
curl "http://localhost:8000/api/v1/documents/search?query=login+issue&limit=3"
```

#### View Prometheus metrics:
```bash
curl http://localhost:8000/api/v1/metrics
```

Or visit Prometheus dashboard at http://localhost:9090.

### Testing the System

1. Ingest knowledge base (if not done yet):
   ```bash
   curl -X POST http://localhost:8000/api/v1/knowledge-base/ingest
   ```

2. Create a test ticket:
   ```bash
   curl -X POST http://localhost:8000/api/v1/tickets \
     -H "Content-Type: application/json" \
     -d '{"description": "My billing information is incorrect"}'
   ```

3. Poll for ticket resolution (worker processes asynchronously):
   ```bash
   # Wait a few seconds, then check
   curl http://localhost:8000/api/v1/tickets/1
   ```

4. Monitor metrics at http://localhost:8000/api/v1/metrics

### Project Structure

```
ticketpilot/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # FastAPI endpoints
│   ├── agents/              # (reserved for future agents)
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── vector_store.py   # Qdrant integration
│   │   ├── embedding.py      # Sentence-transformers embeddings
│   │   └── document_processor.py  # Text chunking & ingestion
│   ├── services/             # (reserved for services)
│   ├── workers/
│   │   ├── __init__.py
│   │   └── worker.py        # Ticket processing worker
│   ├── models.py           # SQLAlchemy models
│   ├── database.py         # Database session
│   ├── metrics.py          # Prometheus metrics
│   └── main.py            # FastAPI app initialization
├── n8n/                   # (n8n workflows - skipped per user request)
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Roadmap

- [x] Project setup
- [x] PostgreSQL persistence (SQLAlchemy)
- [x] Core API endpoints (tickets, documents, metrics)
- [x] Redis event publishing
- [x] LangChain worker with OpenRouter
- [x] RAG pipeline (Qdrant, embeddings, document processing)
- [x] Prometheus metrics (token usage, latency, ticket counts)
- [x] Cost optimization (Redis caching, model selection)
- [ ] n8n workflow - SKIPPED per user request
- [ ] Unit tests
- [ ] Frontend dashboard (optional)

## License

MIT

## Author

Built for AI Engineer portfolio demonstration.
