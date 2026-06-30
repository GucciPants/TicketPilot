# Phase 1 Progress

## Task 1.1: LLM-based hallucination detection ✅
- [x] Replace regex _detect_hallucinations() with LLM fact-checking
- [x] LLM extracts factual claims, verifies against context_docs
- [x] Returns structured warnings with claim + reason
- [x] Sets critical_issues=True if 3+ unsupported claims
- [x] Word count heuristic kept as secondary check
- [x] Fallback to regex heuristics if LLM call fails

## Task 1.2: Confidence scoring re-weight ✅
- [x] 40% LLM assessment (was 20%)
- [x] 30% hallucination check (was penalty-based)
- [x] 20% citation score (was 30%)
- [x] 10% neutral baseline

## Task 1.3: Eval framework ✅
- [x] Runs all 25 gold tickets (--tickets flag still works for limiting)
- [x] max_wait increased to 600s
- [x] Added escalation_rate to summary metrics
- [x] Added avg_response_length metric
- [x] API_BASE configurable via --api-url arg and EVAL_API_URL env
- [x] Better error handling per ticket (non-fatal on KB ingest failure)
- [x] KB ingest moved before loop (runs once, not per-first-ticket)
