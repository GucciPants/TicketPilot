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

1. Clone the repository
2. Copy `.env.example` to `.env` and set your OpenRouter API key
3. Run `docker-compose up -d`
4. Access the API at `http://localhost:8000`
5. Access n8n at `http://localhost:5678`

## Roadmap

- [x] Project setup
- [ ] REST API for ticket ingestion
- [ ] Redis event publishing
- [ ] n8n workflow for ticket routing
- [ ] RAG pipeline with Qdrant
- [ ] AI agent for ticket resolution
- [ ] Prometheus metrics
- [ ] Cost optimization (caching, model selection)
- [ ] Frontend dashboard (optional)

## License

MIT

## Author

Built for AI Engineer portfolio demonstration.
