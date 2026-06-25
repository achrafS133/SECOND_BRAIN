"""Run enterprise QA benchmark against live or in-process CogOS."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from second_brain.config import get_settings
from second_brain.eval.metrics.scorers import aggregate_results, score_case
from second_brain.schemas import BenchmarkCase
from second_brain.services.container import ServiceContainer

logger = logging.getLogger(__name__)


async def run_benchmark(dataset_path: Path | None = None) -> dict:
    dataset_path = dataset_path or Path("eval/benchmarks/enterprise_qa.json")
    cases = [BenchmarkCase(**row) for row in json.loads(dataset_path.read_text(encoding="utf-8"))]

    settings = get_settings()
    container = ServiceContainer(settings)
    await container.startup()

    results = []
    for case in cases:
        start = time.perf_counter()
        response = await container.cogos.run(query=case.query, session_id=f"bench-{case.id}")
        latency_ms = (time.perf_counter() - start) * 1000
        results.append(score_case(case, response, latency_ms))
        logger.info(
            "Case %s faithfulness=%.2f relevance=%.2f latency=%.0fms",
            case.id,
            results[-1].faithfulness,
            results[-1].answer_relevance,
            latency_ms,
        )

    await container.shutdown()
    summary = aggregate_results(results)
    return {
        "summary": summary,
        "results": [r.model_dump() for r in results],
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    output = asyncio.run(run_benchmark())
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
