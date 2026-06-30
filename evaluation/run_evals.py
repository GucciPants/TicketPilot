#!/usr/bin/env python3
"""Run evaluation of the TicketPilot multi-agent pipeline against gold dataset.

Usage:
    python -m evaluation.run_evals [--tickets N] [--output results.json] [--api-url URL]

Requires:
    - Docker containers running (api, worker, db, redis, qdrant)
    - Gold dataset at evaluation/gold_dataset.jsonl
"""
import json
import os
import sys
import time
import argparse
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.metrics import evaluate_single, summarize_results
import requests

API_BASE = os.getenv("EVAL_API_URL", "http://localhost:8000/api/v1")


def wait_for_processing(ticket_id: int, max_wait: int = 600, interval: int = 5) -> dict:
    """Poll until ticket is resolved or escalated."""
    for _ in range(max_wait // interval):
        try:
            resp = requests.get(f"{API_BASE}/tickets/{ticket_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data["status"] in ("resolved", "escalated"):
                    return data
        except requests.RequestException as e:
            print(f"  ⚠️  Poll error for ticket {ticket_id}: {e}")
        time.sleep(interval)
    return None


def run_evaluation(gold_data: list, verbose: bool = False) -> list:
    """Run the full evaluation pipeline."""
    results = []

    # Step 0: Ingest knowledge base once before any tickets
    try:
        ingest_resp = requests.post(f"{API_BASE}/knowledge-base/ingest", timeout=30)
        if verbose:
            print(f"  KB ingest: {ingest_resp.json()}")
    except Exception as e:
        print(f"  ⚠️  KB ingest failed (non-fatal): {e}")

    for i, item in enumerate(gold_data):
        ticket_id = item["ticket_id"]
        description = item["description"]

        if verbose:
            print(f"\n[{i+1}/{len(gold_data)}] {ticket_id}: {description[:60]}...")

        try:
            # Step 1: Create ticket
            create_resp = requests.post(
                f"{API_BASE}/tickets",
                json={"description": description},
                timeout=15
            )
            if create_resp.status_code != 200:
                if verbose:
                    print(f"  ❌ Create failed: {create_resp.text}")
                results.append({
                    "ticket_id": ticket_id,
                    "error": f"Create failed: {create_resp.text}",
                    "status": "error"
                })
                continue

            db_id = create_resp.json()["id"]
            if verbose:
                print(f"  Ticket #{db_id} created")

            # Step 2: Wait for processing
            ticket_data = wait_for_processing(db_id)
            if not ticket_data:
                if verbose:
                    print(f"  ⏰ Timeout waiting for processing")
                results.append({
                    "ticket_id": ticket_id,
                    "error": "Timeout",
                    "status": "error"
                })
                continue

            # Step 3: Get RAG context if available
            try:
                search_resp = requests.get(
                    f"{API_BASE}/documents/search",
                    params={"query": description, "limit": 3},
                    timeout=10
                )
                context_docs = search_resp.json().get("results", []) if search_resp.status_code == 200 else []
            except Exception:
                context_docs = []

            # Step 4: Evaluate
            resolution = ticket_data.get("resolution", "")
            eval_result = evaluate_single(
                generated=resolution,
                expected_resolution=item.get("expected_resolution", ""),
                expected_keywords=item.get("expected_keywords", []),
                context_docs=context_docs
            )

            eval_result["ticket_id"] = ticket_id
            eval_result["db_id"] = db_id
            eval_result["status"] = ticket_data["status"]
            eval_result["resolution_length"] = len(resolution)

            results.append(eval_result)

            if verbose:
                print(f"  Status: {ticket_data['status']}")
                print(f"  Keyword coverage: {eval_result['keyword_coverage']:.1%}")
                print(f"  ROUGE-L F1: {eval_result['rouge_l_f1']:.3f}")
                print(f"  Retrieval hitrate: {eval_result.get('retrieval_hitrate', 0):.1%}")
                if eval_result.get("missing_keywords"):
                    print(f"  Missing keywords: {eval_result['missing_keywords']}")

        except Exception as e:
            if verbose:
                print(f"  ❌ Error: {e}")
            results.append({"ticket_id": ticket_id, "error": str(e), "status": "error"})

        # Small delay between tickets to avoid overwhelming the pipeline
        time.sleep(3)

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate TicketPilot pipeline")
    parser.add_argument("--tickets", type=int, default=0, help="Number of tickets to evaluate (0 = all)")
    parser.add_argument("--output", default="evaluation/results.json", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--api-url", default=API_BASE, help="API base URL (default: %(default)s)")
    args = parser.parse_args()

    # Allow env override
    global API_BASE
    API_BASE = args.api_url

    # Load gold dataset
    dataset_path = os.path.join(os.path.dirname(__file__), "gold_dataset.jsonl")
    with open(dataset_path) as f:
        gold_data = [json.loads(line) for line in f if line.strip()]

    if args.tickets > 0:
        gold_data = gold_data[:args.tickets]

    print(f"📊 Loading {len(gold_data)} evaluation tickets from {dataset_path}")
    print(f"🌐 API: {API_BASE}")

    # Check API health
    try:
        health = requests.get(f"{API_BASE}/health", timeout=5)
        assert health.status_code == 200
        print(f"✅ API healthy: {health.json()}")
    except Exception as e:
        print(f"❌ API not reachable: {e}")
        print("   Make sure Docker containers are running: docker-compose up -d")
        sys.exit(1)

    # Run evaluation
    print(f"\n🚀 Running evaluation...")
    results = run_evaluation(gold_data, verbose=args.verbose)

    # Summarize
    summary = summarize_results(results)

    print(f"\n{'='*50}")
    print(f"📊 EVALUATION RESULTS")
    print(f"{'='*50}")
    print(f"  Tickets evaluated: {summary.get('total_evaluated', 0)}")
    print(f"  Successful: {summary.get('successful', 0)}")
    print(f"  Errors: {summary.get('errors', 0)}")
    print(f"  Escalation rate: {summary.get('escalation_rate', 0):.1%}")
    print(f"  Avg keyword coverage: {summary.get('avg_keyword_coverage', 0):.1%}")
    print(f"  Avg ROUGE-L F1: {summary.get('avg_rouge_l_f1', 0):.3f}")
    print(f"  Avg retrieval hitrate: {summary.get('avg_retrieval_hitrate', 0):.1%}")
    print(f"  Avg response length: {summary.get('avg_response_length', 0):.0f} chars")
    print(f"  Exact match rate: {summary.get('exact_match_rate', 0):.1%}")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": {"tickets_evaluated": len(gold_data)},
        "summary": summary,
        "results": results
    }

    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n📁 Results saved to: {args.output}")

    # Return non-zero if results are poor
    if summary.get("avg_keyword_coverage", 0) < 0.3:
        print("\n⚠️  Warning: Low keyword coverage detected")
        sys.exit(1)


if __name__ == "__main__":
    main()
