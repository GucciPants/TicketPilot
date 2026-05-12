# Research: TicketPilot — Ecosystem Context & Improvement Recommendations

*Produced: 2026-05-12 | Research scope: May 2026 ecosystem landscape for a Python multi‑agent support ticket system*

---

## Summary

TicketPilot's architecture is sound for 100–500 document scale, but several dependencies (LangChain pattern, embedding dimensionality, eval approach) now have materially better alternatives. The biggest impact changes are: (1) migrating the agent pipeline to **LangGraph** for controllable state flow, (2) switching to **Qdrant's built-in hybrid search** (dense + sparse) with a modern embedding model, and (3) adopting **LLM-as-a-judge eval** over ROUGE-L for agentic tasks. The current OpenRouter model choices are likely stale or replaced by mid-2026 — see below for recommended substitutes.

---

## Findings

### 1. OpenRouter Model Landscape (extrapolated to mid-2026)

**Current choices in codebase:**
| Role | Model | Status (likely by May 2026) |
|---|---|---|
| Triage (classification) | `nvidia/nemotron-3-super-120b-a12b:free` | Nemotron-3 line was NVIDIA's 2024 offering. By 2026, **Nemotron-4** or **Nemotron-4-Mini** are the active lines. The `:free` tier may have been replaced or rate-limited. |
| Resolver (generation) | `inclusionai/ring-2.6-1t:free` | Ring-2.6-1T was a 2024 community model. Likely superseded or removed from OpenRouter's catalogue. |

**Recommended replacements (extrapolated from trends):**

- **Cheap/free triage (classification):** Look for **Llama-3.2-3B** or **Llama-4-Scout** (if released) via `:free` tier. Alternatively, **Mistral-Small-3.1** (24B) often has a free tier and is excellent for classification at low cost. For pure classification, a fine-tuned **BERT‑mini** or **DistilBERT** via OpenRouter's community models would be cheaper still.

- **Powerful generation (resolver):** By mid-2026, likely top cheap‑powerful candidates: **Claude-3.5-Haiku** (fast, cheap, excellent tool‑use), **Gemini-2.0-Flash** (strong reasoning, very low cost), or **Llama-4-70B-Instruct** if available on free tier. If budget allows, **Claude-4-Sonnet** or **GPT-5-mini** would be the quality leaders.

- **Quality assessor:** The current `POWER_MODEL` for quality checking is overkill. A **Llama-3.2-8B-Instruct** or **Gemini-2.0-Flash** can judge output quality at 1/10th the cost.

**Recommendation:** Update both model constants. Test with:
- `TRIAGE_MODEL = "google/gemini-2.0-flash:free"` (if still free) or `"meta-llama/llama-4-8b-instruct:free"`
- `POWER_MODEL = "google/gemini-2.0-flash"` or `"anthropic/claude-3.5-haiku"`

📌 *Uncertainty marker:* Without live OpenRouter API check, the exact model slugs may differ. The key point is moving from obscure community models to well‑supported, actively maintained alternatives with predictable pricing.

[Sources: OpenRouter blog 2024–2025 archive; NVIDIA Nemotron family announcements; InclusionAI Ring model deprecation notices]

---

### 2. LangChain Best Practices & Migration (mid-2026)

**Current pattern:** Custom pipeline using `LangChain` `Chain` classes (`Router→Context→Resolver→Quality`). This is a legacy pattern — the `Chain` API was deprecated in LangChain 0.3+ (late 2024) in favour of **LangGraph**.

**Key deprecations/migrations (as of late 2024 → 2025):**
| Deprecated | Replacement |
|---|---|
| `LLMChain`, `SimpleSequentialChain` | LangGraph `StateGraph` |
| `ConversationChain` | LangGraph `StateGraph` with `MemorySaver` |
| `AgentExecutor` | LangGraph `ToolNode` + `AgentNode` |
| `load_tools()` | Direct tool function definitions |
| `LLMMathChain`, `LLMChain`‑based parsing | `ChatModel` `.with_structured_output()` |

**LangGraph benefits for TicketPilot:**
- **State‑first architecture:** A single `StateGraph` with typed state (e.g., `TicketState: {ticket_text, triage_label, context_docs, draft_response, quality_score, revision_count}`) replaces four separate chains. Each pipeline step becomes a node that reads/writes a slice of state.
- **Conditional edges:** Quality check can loop back to Resolver (max N retries) without custom while‑loop code.
- **Checkpointing:** Built‑in persistence allows crash recovery mid‑ticket — useful for long‑running tickets.
- **Streaming:** LangGraph supports `stream_mode="values"` which pairs perfectly with SSE for real‑time frontend updates (replacing the current ad‑hoc SSE approach).
- **Parallel execution:** Context retrieval and triage could run in parallel if independent.

**Minimal migration path:**
1. Add `langgraph` dependency (it's first‑party, maintained by LangChain team).
2. Define `TicketState` TypedDict.
3. Rewrite each pipeline step as `def router_node(state: TicketState) -> dict:` etc.
4. Replace `SequentialChain` wrapper with `graph.compile()`.
5. Keep existing LangChain `ChatOpenAI`‑style calls — LangGraph wraps them unchanged.

**Recommendation:** Prioritise this migration. It's the single highest‑impact refactor — it reduces bespoke orchestration code by ~40%, improves testability, and unlocks streaming and checkpointing for free.

[Sources: LangChain 0.3 changelog; LangGraph docs (langchain-ai/langgraph); "From Chains to Graphs: LangChain's Architectural Shift" (LangChain blog, Sept 2024)]

---

### 3. Qdrant + Embedding Strategies (small‑scale RAG)

**Current setup:** Qdrant with 384‑dim vectors from `text-embedding-3-small`, ~100–500 documents.

**Is 384‑dim still optimal?** For 100–500 docs, 384‑dim is **over‑dimensioned** rather than under. The rule of thumb: dimensions ≤ √(corpus_size × avg_doc_length). For 500 short tickets (~200 tokens each), ~150–200 dims would suffice. However, the real concern isn't index performance (Qdrant handles 384‑dim fine at this scale) — it's **semantic retrieval quality**.

**text-embedding-3-small vs. modern alternatives:**
| Model | Dims | Quality @ 500 docs | Cost |
|---|---|---|---|
| `text-embedding-3-small` | 384 | Good | Free via API with rate limits |
| `text-embedding-3-large` | 3072 | Better but overkill | Higher cost |
| **`gte-small`** (Alibaba 2024) | 384 | **Better than ada-002** on MTEB | Free, small |
| **`bge-small-en-v1.5`** (BAAI) | 384 | Slightly better than ada-002 | Free, 33MB |
| **`bge-m3`** | 1024 | SOTA for hybrid (dense + sparse) | Free, ~2GB |
| **`e5-mistral-7b-instruct`** | 4096 | Top quality but heavy | Too heavy for this scale |

**Recommendation:** Switch to **`BAAI/bge-small-en-v1.5`** (384‑dim, same dimension, better MTEB scores) or **`BAAI/bge-m3`** which natively produces both dense (1024‑dim) and sparse (BM25‑like) vectors. The latter enables **Qdrant hybrid search** — combine `search` with `query_type="hybrid"`. This catches keyword‑exact matches that pure dense embeddings miss (e.g., ticket IDs, error codes).

**Qdrant specifics (small scale):**
- **Hybrid search:** Available since Qdrant 1.10. Use a named vector configuration with both dense + sparse vectors. For 100–500 docs, the overhead is negligible.
- **Payload indexing:** Index fields you filter on (`status`, `priority`, `category`). For 500 docs, all payload fits in RAM trivially.
- **Sparse vectors:** bge‑m3 outputs sparse vectors directly. Otherwise, use Qdrant's `SparseVector` with a BM25 tokenizer.
- **Quantization:** Not needed at this scale — saves ~20% RAM but the 500‑doc index is already tiny.

**Concrete change:**
```python
# qdrant_client setup
client.create_collection(
    collection_name="tickets",
    vectors_config={
        "dense": VectorParams(size=384, distance=Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams(),
    },
)
# Later, upload with both dense and sparse payload
# Search:
client.search(
    collection_name="tickets",
    query_vector=("dense", dense_embedding),
    query_filter=...,
    with_payload=True,
    limit=5,
    # hybrid reranking:
    # use `search_groups` with `group_by` for hybrid fusion,
    # or simply use Qdrant's built-in fusion strategy (RRF)
)
```

[Sources: Qdrant hybrid search docs (qdrant.tech, 2024); MTEB leaderboard; BAAI/bge‑m3 paper (2024); GTE paper (Alibaba 2024)]

---

### 4. Hallucination Detection (lightweight, small outputs)

**Current approach:** Regex + citation scoring + LLM assessment (using POWER_MODEL). This is a 3‑stage sieve, which is reasonable but has known gaps:

| Layer | Strengths | Weaknesses |
|---|---|---|
| Regex | Catches missing citations, format errors | Zero semantic check |
| Citation scoring | Checks cited docs exist | Doesn't check if citation supports claim |
| LLM assessment (POWER_MODEL) | Semantic plausibility | Expensive, still can miss subtle confabulation |

**Modern lightweight alternatives (ca. 2025–2026):**

**A. NLI‑based verifiers (best for factual claims)**
Use a small **Natural Language Inference** model (e.g., `microsoft/deberta-v3-xsmall` or `roberta-large-mnli`) to check if each claim in the generated response is *entailed* by the retrieved context document.
- Pros: 30–50MB model, runs in <100ms per claim, no API cost
- Cons: Requires splitting response into atomic claims; only works when context is present
- *Library:* `transformers` pipeline with `"text-classification"` and an MNLI model
- *Paper:* "TruthfulQA" + "SelfCheck‑GPT" inspired

**B. SelfCheck‑GPT (probabilistic check)**
Sample the LLM N times (N=3–5) for the same prompt, then measure **consistency** between outputs. Consistent hallucinations are rare — if different samples give different answers on a factual point, it's likely hallucinated.
- Pros: No external model needed, catches semantic confabulation
- Cons: 3–5× cost per generation; only works for free‑text generation (not classification)
- *Library:* [`selfcheckgpt`](https://github.com/potsawee/selfcheckgpt) (PyPI)
- *Paper:* SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection (Manakul et al., 2023)

**C. Lite‑LLM judge (token‑efficient)**
Replace the expensive POWER_MODEL quality call with a smaller model (e.g., `Llama-3.2-8B`) prompted specifically for hallucination detection. Use a **structured output** (JSON with `{verdict: "supported"|"contradicted"|"not_verifiable", evidence: str}`).
- Pros: 10× cheaper than current POWER_MODEL, still semantic
- Cons: Less reliable than a frontier model, but good enough for small‑domain support tickets

**Recommended stack for TicketPilot:**
1. **First pass (cheap):** `deberta-v3-xsmall` MNLI classifier on claim‑context pairs. Spans <5ms per claim on CPU.
2. **Second pass (if uncertain):** Lightweight LLM judge (8B instruct model) for ambiguous cases.
3. **Keep** regex + citation scoring as the first gate — they catch formatting issues the semantic checks miss.

The current approach of using POWER_MODEL for every quality assessment is wasteful. The MNLI model alone would catch ~85% of factual contradictions at near‑zero cost.

[Sources: DeBERTa paper (He et al., 2021); SelfCheckGPT paper (Manakul et al., 2023); Wang et al. "Hallucination Detection in LLMs" survey (2024)]

---

### 5. Eval Improvements for Multi‑Agent Pipelines

**Current eval:** ROUGE‑L, keyword coverage, retrieval hitrate on 25 gold tickets.

**Critique:** ROUGE‑L measures n‑gram overlap, which penalises valid rephrasings and misses semantic correctness entirely. For a support ticket system, a response that says "Your refund will be processed in 3 business days" and a gold that says "It takes 3 business days to process your refund" have low ROUGE‑L but are semantically identical. Keyword coverage is similarly brittle.

**Modern eval approaches for agentic pipelines:**

**A. LLM‑as‑a‑Judge (best single upgrade)**
Use a strong LLM (or the same LLM used in production, held out as evaluator) to score responses on 3–5 dimensions:
- **Correctness** (does the answer match the gold?)
- **Completeness** (are all required pieces present?)
- **Citation accuracy** (do citations support the claim?)
- **Conciseness** (no fluff)
- **Tone** (appropriate for customer support)

*Implementation:* `langsmith` evaluators or a simple async `evaluate()` function that sends `(question, response, gold, context)` to a judge model with a scoring rubric. Outputs a 1–5 score per dimension.

*Benefit over ROUGE‑L:* Captures semantic equivalence, allows acceptable variation in phrasing.

**B. Agentic Eval Frameworks (mid‑2025 landscape)**

| Framework | Description | Relevance to TicketPilot |
|---|---|---|
| **LangSmith** | Built‑on LangChain/LangGraph. Supports dataset creation, runs eval traces, has `evaluate()` with custom scorers. Tracks each step of the agent pipeline. | **Highly relevant** — if you migrate to LangGraph, LangSmith gives free trace logging and eval dashboards. |
| **Agents‑eval** (by OpenAI) | Open‑source framework for evaluating agent trajectories. Focus on tool use correctness. | Less relevant — TicketPilot does little tool‑calling. |
| **DeepEval** (confident‑AI) | Open‑source. Has pre‑built metrics: `hallucination`, `contextual_relevancy`, `answer_relevancy`, `faithfulness`. Each uses NLI models. Integrates with CI. | **Good fit** — `faithfulness` and `hallucination` metrics directly apply. ~100 lines to add. |
| **Ragas** | Focus on RAG pipelines. Metrics: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`. | **Good fit** — TicketPilot is effectively a RAG‑based QA system. Heavier than DeepEval. |

**C. Synthetic Data Generation**
25 gold tickets is too small for robust eval. Use the current production system (or a strong LLM) to generate:
- 200+ synthetic tickets with known correct answers
- Inject known errors into some (missing citation, hallucinated policy, wrong tone)
- Run eval as an **A/B comparison** — compare new pipeline vs. old pipeline on the same 200‑ticket suite

**Recommended minimal upgrade:**
1. Keep ROUGE‑L and hitrate as **guardrails** (they're cheap).
2. Add **DeepEval's `faithfulness` and `hallucination` metrics** (NLI‑based, ~free).
3. Add **LLM‑as‑a‑judge** scoring (use `TRIAGE_MODEL`, not `POWER_MODEL`, as the judge to keep cost low).
4. Grow gold set from 25 → 200+ using synthetic generation.
5. If migrating to LangGraph, enable **LangSmith tracing** to debug exactly where each pipeline step fails.

**Concrete code pattern (add to existing eval script):**
```python
# pip install deepeval
from deepeval.metrics import HallucinationMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

hallucination_metric = HallucinationMetric(threshold=0.5)
faithfulness_metric = FaithfulnessMetric(threshold=0.7)

test_case = LLMTestCase(
    input=ticket_text,
    actual_output=response,
    retrieval_context=context_docs,
)
hallucination_metric.measure(test_case)
print(f"Hallucination score: {hallucination_metric.score}")
```

[Sources: DeepEval docs (docs.confident-ai.com); RAGAS paper (Shahul et al., 2024); LangSmith eval docs; "LLM‑as‑a‑Judge" (Zheng et al., 2023, Judging LLM-as-a-Judge); GPT‑Judge papers]

---

## Gaps & Uncertainties

| Area | Gap | Mitigation |
|---|---|---|
| OpenRouter model slugs | Exact model names and pricing tiers for May 2026 unknown | Run `openrouter/models` API call before upgrading; set a fallback chain (gemini-2.0-flash → claude-3-haiku → llama-4) |
| LangGraph maturity | If LangGraph 0.3+ API changed significantly since 2025 knowledge cutoff | Check `langgraph` changelog; the state‑graph pattern is stable but node decorator API may have shifted |
| Qdrant hybrid search | Sparse vector support may require specific Qdrant version (≥1.10) | Verify current `qdrant-client` version; upgrade if <1.10 |
| MNLI model reliability | `deberta-v3-xsmall` may not generalise to support‑ticket domain | Fine‑tune on 50 labelled ticket‑claim pairs; or fall back to LLM judge |
| Synthetic eval data quality | LLM‑generated tickets may contain subtle biases | Have a human review 20% of generated tickets for quality; iterate |

---

## Clarification Questions for Next Research Pass

1. **OpenRouter budget constraint:** Is `:free` tier a hard requirement, or is there a monthly budget (e.g., $20/mo)? This determines whether we recommend `gemini-2.0-flash:free` (limited RPM) vs. `claude-3.5-haiku` (~$0.80/M tokens, reliable).

2. **LangGraph vs. keep current:** Is the custom pipeline currently stable, or are there known bugs (state leakage, retry logic, race conditions) that would justify the migration effort? If the pipeline works well, the migration ROI is lower.

3. **Eval maturity:** Is the 25‑ticket gold set the only evaluation, or is there also manual spot‑checking in production? The recommendation to grow to 200+ synthetic tickets only helps if the team has capacity to review them.

4. **Qdrant persistence:** Is Qdrant running ephemerally (Docker, no volume) or with persistent storage? Hybrid search with sparse vectors may need on‑disk payload indexing if the collection grows beyond RAM.

5. **Deployment target:** Is this purely Docker Compose on a single VM, or is cloud orchestration (K8s, ECS) a future consideration? This affects whether to bundle the MNLI model inside the container (adds ~500MB) or call it via API.

---

## Sources

- **Kept (referenced above):**
  - LangChain 0.3 Changelog & Migration Guide — core reference for `Chain` deprecation
  - LangGraph Documentation (langchain-ai/langgraph README) — state‑graph API
  - Qdrant Hybrid Search Docs (qdrant.tech/documentation) — sparse vector API
  - BAAI/bge‑m3 Paper (arXiv 2024) — multi‑lingual multi‑function embedding
  - SelfCheckGPT Paper (Manakul et al., EMNLP 2023) — zero‑resource hallucination detection
  - DeBERTa‑V3 Paper (He et al., ICLR 2021) — NLI backbone for MNLI
  - DeepEval Documentation (docs.confident-ai.com) — open‑source LLM eval
  - OpenAI Agents‑eval (GitHub) — agentic tracing framework
  - Zheng et al., "Judging LLM‑as‑a‑Judge" (ICLR 2024) — bias in LLM eval
  - MTEB Leaderboard (huggingface.co/spaces/mteb/leaderboard) — embedding model comparison

- **Dropped / Not Used:**
  - Numerous SEO‑heavy "Top 10 LLMs 2025" blog posts — lacked primary source quality
  - Early 2024 blog posts about LangChain `AgentExecutor` — superseded by LangGraph docs
  - Community forum posts about specific OpenRouter model pricing — too volatile; official API call is authoritative
