from __future__ import annotations

import re
import time

from second_brain.schemas import BenchmarkCase, BenchmarkResult, EvidencePackage, QueryResponse


def keyword_faithfulness(answer: str, evidence: EvidencePackage | None, keywords: list[str]) -> float:
    if not keywords:
        return 1.0 if answer.strip() else 0.0
    answer_lower = answer.lower()
    evidence_text = ""
    if evidence:
        evidence_text = " ".join(
            str(n.properties.get("text", "")) for n in evidence.nodes
        ).lower()
    hits = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in answer_lower and (not evidence_text or kw_lower in evidence_text):
            hits += 1
        elif kw_lower in answer_lower and not evidence:
            hits += 0.5
    return hits / len(keywords)


def answer_relevance(query: str, answer: str, expected_keywords: list[str]) -> float:
    if not answer.strip():
        return 0.0
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    answer_tokens = set(re.findall(r"[a-z0-9]+", answer.lower()))
    overlap = len(query_tokens & answer_tokens) / max(1, len(query_tokens))

    keyword_hits = 0
    if expected_keywords:
        keyword_hits = sum(1 for k in expected_keywords if k.lower() in answer.lower())
        keyword_hits /= len(expected_keywords)
    return 0.5 * overlap + 0.5 * (keyword_hits if expected_keywords else overlap)


def graph_grounding(answer: str, evidence: EvidencePackage | None, entities: list[str]) -> float:
    if not entities:
        return 1.0
    answer_lower = answer.lower()
    evidence_text = ""
    if evidence:
        evidence_text = " ".join(
            str(n.properties.get("text", "")) for n in evidence.nodes
        ).lower()
    hits = 0
    for entity in entities:
        el = entity.lower()
        if el in answer_lower and (el in evidence_text or not evidence):
            hits += 1
    return hits / len(entities)


def score_case(
    case: BenchmarkCase,
    response: QueryResponse,
    latency_ms: float,
) -> BenchmarkResult:
    return BenchmarkResult(
        case_id=case.id,
        query=case.query,
        answer=response.answer,
        faithfulness=keyword_faithfulness(
            response.answer, response.evidence, case.expected_keywords
        ),
        answer_relevance=answer_relevance(
            case.query, response.answer, case.expected_keywords
        ),
        graph_grounding=graph_grounding(
            response.answer, response.evidence, case.expected_entities
        ),
        latency_ms=latency_ms,
    )


def aggregate_results(results: list[BenchmarkResult]) -> dict:
    if not results:
        return {"count": 0}
    n = len(results)
    return {
        "count": n,
        "faithfulness": round(sum(r.faithfulness for r in results) / n, 4),
        "answer_relevance": round(sum(r.answer_relevance for r in results) / n, 4),
        "graph_grounding": round(sum(r.graph_grounding for r in results) / n, 4),
        "latency_ms_p50": round(sorted(r.latency_ms for r in results)[n // 2], 2),
        "latency_ms_p99": round(sorted(r.latency_ms for r in results)[max(0, int(n * 0.99) - 1)], 2),
    }
