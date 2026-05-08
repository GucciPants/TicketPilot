"""Evaluation metrics for TicketPilot."""
import json
import re
from typing import List, Dict

def normalize(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def keyword_coverage(generated: str, expected_keywords: List[str]) -> Dict:
    """Measure how many expected keywords appear in the generated response."""
    gen_lower = generated.lower()
    found = [kw for kw in expected_keywords if kw.lower() in gen_lower]
    return {
        "total_keywords": len(expected_keywords),
        "found_keywords": len(found),
        "missing_keywords": [kw for kw in expected_keywords if kw.lower() not in gen_lower],
        "coverage": len(found) / len(expected_keywords) if expected_keywords else 1.0
    }

def exact_match(generated: str, expected: str) -> bool:
    """Check if generated response contains the core information from expected."""
    gen_norm = normalize(generated)
    exp_norm = normalize(expected)
    # Check if key phrases from expected appear in generated
    exp_sentences = [s.strip() for s in exp_norm.split('.') if len(s.strip()) > 20]
    if not exp_sentences:
        return False
    matched = sum(1 for s in exp_sentences if s in gen_norm)
    return matched / len(exp_sentences) >= 0.3  # 30% sentence overlap threshold


def retrieval_hitrate(context_docs: List[Dict], expected_keywords: List[str]) -> float:
    """Measure if retrieved documents contain expected keywords."""
    if not context_docs or not expected_keywords:
        return 0.0
    all_context_text = ' '.join(d.get('text', '') for d in context_docs).lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in all_context_text)
    return found / len(expected_keywords)


def rouge_l_similarity(generated: str, expected: str) -> float:
    """Simplified ROUGE-L inspired metric based on longest common subsequence."""
    gen_words = normalize(generated).split()
    exp_words = normalize(expected).split()
    
    if not gen_words or not exp_words:
        return 0.0
    
    # Simple LCS implementation
    m, n = len(gen_words), len(exp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if gen_words[i-1] == exp_words[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    lcs = dp[m][n]
    precision = lcs / len(gen_words) if gen_words else 0
    recall = lcs / len(exp_words) if exp_words else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return f1


def evaluate_single(generated: str, expected_resolution: str, expected_keywords: List[str], context_docs: List[Dict] = None) -> Dict:
    """Run all metrics on a single evaluation pair."""
    kw = keyword_coverage(generated, expected_keywords)
    return {
        "keyword_coverage": kw["coverage"],
        "found_keywords": kw["found_keywords"],
        "missing_keywords": kw["missing_keywords"],
        "exact_match": exact_match(generated, expected_resolution),
        "rouge_l_f1": rouge_l_similarity(generated, expected_resolution),
        "retrieval_hitrate": retrieval_hitrate(context_docs or [], expected_keywords)
    }


def summarize_results(results: List[Dict]) -> Dict:
    """Aggregate results across all evaluation items."""
    n = len(results)
    if n == 0:
        return {}
    
    return {
        "total_evaluated": n,
        "avg_keyword_coverage": sum(r["keyword_coverage"] for r in results) / n,
        "avg_rouge_l_f1": sum(r["rouge_l_f1"] for r in results) / n,
        "avg_retrieval_hitrate": sum(r.get("retrieval_hitrate", 0) for r in results) / n,
        "exact_match_rate": sum(1 for r in results if r["exact_match"]) / n,
        "total_keywords_found": sum(r["found_keywords"] for r in results),
        "total_keywords_expected": sum(r["found_keywords"] + len(r.get("missing_keywords", [])) for r in results)
    }
