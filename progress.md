# TicketPilot Progress

## Latest Results (2026-06-30)

### Model: deepseek/deepseek-v4-flash via OpenRouter
### Pipeline: Async event-driven (Redis Streams)

### 25-Ticket Evaluation Summary

| Metric | Original | After Phase 0-4 | **Async Pipeline** | Improvement |
|--------|:--------:|:----------------:|:------------------:|:-----------:|
| **ROUGE-L F1** | 3.9% | 12.1% | **50.7%** 🚀 | +1200% |
| **Keyword coverage** | 66% | 69.3% | 53.3% | — |
| **Retrieval hitrate** | 33% | 82.7% | **78.7%** 🎯 | +139% |
| **Escalation rate** | 100% | 64% | **16%** 🎯 | -84% |
| **Exact match** | 0% | 0% | 0% | — |
| **Avg response length** | ~3500 | 1109 | 196 chars | shorter |
| **Errors** | — | 0 | **0/25** ✅ | — |
| **Runtime** | — | ~25 min | **~10 min** 🏎️ | 2.5x faster |

### Optimization Phases

| Phase | What | Impact |
|-------|------|--------|
| Phase 0 | Retry + timeouts | Zero errors |
| Phase 1 | Hallucination detection (LLM), eval | Escalation 100%→60% |
| Phase 2 | Health checks, LLMFactory, Alembic | Production readiness |
| Phase 3 | SSE opt, worker parallelization | Throughput up |
| Phase 4 | LangChain 0.3.x, ContextAgent refactor | Code quality |
| KB v2 | Gold standards in vector store | Retrieval 33%→82% |
| Async | Redis Stream event-driven pipeline | 2.5x throughput, ROUGE-L 50% |

### Components

| Component | Status | Notes |
|-----------|--------|-------|
| API | ✅ | FastAPI, port 8002 |
| DB | ✅ | PostgreSQL 16 |
| Redis | ✅ | Port 6380 (ext), 6379 (int) |
| Qdrant | ✅ | Vector DB, port 6333 |
| Prometheus | ✅ | Port 9090 |
| Async Worker | ✅ | Event-driven, 4 concurrency/stage |
| Sync Worker | ⚠️ Legacy | `--profile legacy` |

### Tests: 55/55 ✅
- 9 agent tests
- 20 API tests
- 26 auth tests
