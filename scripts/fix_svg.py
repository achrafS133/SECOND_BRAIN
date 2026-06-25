"""Sanitize SVG files for GitHub preview (valid XML, ASCII-safe text)."""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "docs" / "diagrams"

REPLACEMENTS = {
    "\ufffd": "",
    "\u2014": " - ",
    "\u2013": "-",
    "\u00b7": " | ",
    "\u00a0": " ",
    "ï¿½": " | ",
}


def sanitize_svg(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    icon_map = {
        'y="306"': "D",
        'y="371"': "C",
        'y="436"': "L",
        'y="611"': "S",
        'y="676"': "F",
        'y="815"': "U",
    }
    for y_attr, letter in icon_map.items():
        pattern = rf'(<text x="106" {y_attr}[^>]*>)[^<]*(</text>)'
        if 'y="815"' in y_attr:
            pattern = rf'(<text x="145" {y_attr}[^>]*>)[^<]*(</text>)'
        text = re.sub(pattern, rf"\1{letter}\2", text)

    title_fixes = {
        "The Second Brain  Query": "The Second Brain - Query",
        "CogOS Runtime  Query Path": "CogOS Runtime - Query Path",
        "EXTERNAL  LLM PROVIDERS": "EXTERNAL - LLM PROVIDERS",
        "OpenAI / Llama / Mistral  Reasoning": "OpenAI / Llama / Mistral - Reasoning",
        "The Second Brain — Data Ingestion Pipeline": "The Second Brain - Data Ingestion Pipeline",
        "Stream-native ingestion | Graph-RAG | Multi-Agent CogOS": "Stream-native ingestion | Graph-RAG | Multi-Agent CogOS",
        "Processing | Memory | Agent orchestration": "Processing | Memory | Agent orchestration",
        "Seconds–minutes TTL": "Seconds-minutes TTL",
    }
    for old, new in title_fixes.items():
        text = text.replace(old, new)

    text = re.sub(r"  +", " ", text)
    path.write_text(text, encoding="utf-8")
    ET.parse(path)
    print(f"OK: {path.relative_to(ROOT)}")


def main() -> int:
    targets = [
        DIAGRAMS / "query-pipeline-aws.svg",
        DIAGRAMS / "ingestion-pipeline-arch.svg",
    ]
    if len(sys.argv) > 1:
        targets = [Path(a) for a in sys.argv[1:]]

    for target in targets:
        sanitize_svg(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
