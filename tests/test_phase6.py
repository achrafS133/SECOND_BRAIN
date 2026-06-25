import asyncio

from second_brain.eval.ablation.config import FLAT_RAG, FULL_COGOS, GRAPH_ONLY
from second_brain.eval.ablation.report import render_ablation_markdown
from second_brain.eval.run_ablation import run_profile
from second_brain.schemas import BenchmarkCase


def test_ablation_profiles_have_expected_flags():
    assert FLAT_RAG.vector_only is True
    assert FLAT_RAG.use_critic is False
    assert GRAPH_ONLY.use_graph_edges is True
    assert GRAPH_ONLY.use_hybrid_scoring is False
    assert FULL_COGOS.use_critic is True


def test_ablation_report_renders_markdown():
    md = render_ablation_markdown(
        {
            "generated_at": "2026-01-01T00:00:00",
            "dataset": "enterprise_qa.json",
            "configurations": [
                {
                    "name": "flat_rag",
                    "summary": {
                        "faithfulness": 0.5,
                        "answer_relevance": 0.6,
                        "graph_grounding": 0.4,
                        "latency_ms_p50": 100,
                    },
                }
            ],
        }
    )
    assert "Ablation Study Report" in md
    assert "flat_rag" in md


async def test_run_profile_flat_rag():
    cases = [
        BenchmarkCase(
            id="t1",
            query="memory tiers",
            expected_keywords=["M0"],
            expected_entities=[],
        )
    ]
    result = await run_profile(FLAT_RAG, cases)
    assert result["name"] == "flat_rag"
    assert result["summary"]["count"] == 1


def test_run_profile_flat_rag_sync():
    asyncio.run(test_run_profile_flat_rag())
