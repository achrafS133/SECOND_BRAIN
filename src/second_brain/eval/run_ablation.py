"""Paper-ready ablation study: flat RAG vs graph vs tiered memory vs full CogOS."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from second_brain.config import Settings, get_settings
from second_brain.eval.ablation.config import ALL_PROFILES, FLAT_RAG, AblationProfile
from second_brain.eval.ablation.report import write_ablation_report
from second_brain.eval.metrics.scorers import aggregate_results, score_case
from second_brain.schemas import BenchmarkCase, IngestDocumentRequest
from second_brain.services.container import ServiceContainer

logger = logging.getLogger(__name__)

CORPUS = [
    IngestDocumentRequest(
        uri="doc://architecture/memory",
        title="Memory Tier Model",
        content=(
            "## Memory Tiers\n"
            "M0 working memory handles IoT streams. M1 short-term is the in-context window. "
            "M2 long-term stores graph and vector memory.\n"
            "CheckoutService depends on PaymentGateway for transaction authorization."
        ),
    ),
    IngestDocumentRequest(
        uri="doc://runbook/latency",
        title="Checkout Latency Runbook",
        content=(
            "## Incident Response\n"
            "If checkout latency spikes, inspect PaymentGateway upstream dependencies "
            "and BillingService deploy events."
        ),
    ),
]


async def _seed_corpus(container: ServiceContainer) -> None:
    for doc in CORPUS:
        await container.ingest_document(doc)


async def run_profile(
    profile: AblationProfile,
    cases: list[BenchmarkCase],
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    container = ServiceContainer(settings, ablation=profile)
    await container.startup()
    await _seed_corpus(container)

    results = []
    for case in cases:
        start = time.perf_counter()
        response = await container.cogos.run(
            query=case.query,
            session_id=f"ablation-{profile.name}-{case.id}",
        )
        latency_ms = (time.perf_counter() - start) * 1000
        results.append(score_case(case, response, latency_ms))

    await container.shutdown()
    summary = aggregate_results(results)
    return {
        "name": profile.name,
        "profile": profile.__dict__,
        "summary": summary,
        "results": [r.model_dump() for r in results],
    }


async def run_ablation_study(
    dataset_path: Path | None = None,
    profiles: list[AblationProfile] | None = None,
    output_dir: Path | None = None,
) -> dict:
    dataset_path = dataset_path or Path("eval/benchmarks/enterprise_qa.json")
    output_dir = output_dir or Path("eval/reports")
    profiles = profiles or ALL_PROFILES
    cases = [BenchmarkCase(**row) for row in json.loads(dataset_path.read_text(encoding="utf-8"))]

    configurations = []
    for profile in profiles:
        logger.info("Running ablation profile: %s", profile.name)
        configurations.append(await run_profile(profile, cases))

    baseline = next((c for c in configurations if c["name"] == FLAT_RAG.name), configurations[0])
    b = baseline["summary"]
    delta_vs_flat: dict[str, dict] = {}
    for cfg in configurations:
        if cfg["name"] == baseline["name"]:
            continue
        s = cfg["summary"]
        delta_vs_flat[cfg["name"]] = {
            "faithfulness": round(s.get("faithfulness", 0) - b.get("faithfulness", 0), 4),
            "answer_relevance": round(s.get("answer_relevance", 0) - b.get("answer_relevance", 0), 4),
            "graph_grounding": round(s.get("graph_grounding", 0) - b.get("graph_grounding", 0), 4),
        }

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "dataset": str(dataset_path),
        "configurations": configurations,
        "delta_vs_flat_rag": delta_vs_flat,
    }
    json_path, md_path = write_ablation_report(report, output_dir)
    report["report_json"] = str(json_path)
    report["report_markdown"] = str(md_path)
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    report = asyncio.run(run_ablation_study())
    print(json.dumps({"summary_paths": {
        "json": report["report_json"],
        "markdown": report["report_markdown"],
    }, "delta_vs_flat_rag": report["delta_vs_flat_rag"]}, indent=2))


if __name__ == "__main__":
    main()
