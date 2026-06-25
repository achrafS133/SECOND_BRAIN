from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def render_ablation_markdown(report: dict) -> str:
    lines = [
        "# The Second Brain — Ablation Study Report",
        "",
        f"Generated: {report.get('generated_at', datetime.utcnow().isoformat())}",
        f"Dataset: `{report.get('dataset', 'enterprise_qa.json')}`",
        "",
        "## Summary",
        "",
        "| Configuration | Faithfulness | Relevance | Graph Grounding | p50 Latency (ms) |",
        "|---|---:|---:|---:|---:|",
    ]

    for row in report.get("configurations", []):
        s = row["summary"]
        lines.append(
            f"| **{row['name']}** | {s.get('faithfulness', 0):.3f} | "
            f"{s.get('answer_relevance', 0):.3f} | {s.get('graph_grounding', 0):.3f} | "
            f"{s.get('latency_ms_p50', 0):.1f} |"
        )

    if report.get("delta_vs_flat_rag"):
        lines.extend(["", "## Δ vs Flat RAG baseline", ""])
        for name, delta in report["delta_vs_flat_rag"].items():
            lines.append(
                f"- **{name}**: faithfulness {delta['faithfulness']:+.3f}, "
                f"relevance {delta['answer_relevance']:+.3f}, "
                f"graph grounding {delta['graph_grounding']:+.3f}"
            )

    lines.extend(["", "## Interpretation", ""])
    lines.append(
        "Higher faithfulness and graph grounding indicate better evidence alignment. "
        "Full CogOS should outperform flat RAG on multi-hop enterprise queries when "
        "the knowledge graph contains relational structure."
    )
    return "\n".join(lines) + "\n"


def write_ablation_report(report: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"ablation_{stamp}.json"
    md_path = output_dir / f"ablation_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_ablation_markdown(report), encoding="utf-8")
    return json_path, md_path
