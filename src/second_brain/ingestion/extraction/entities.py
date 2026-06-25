from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ExtractedEntity:
    name: str
    entity_type: str
    canonical_id: str


@dataclass
class ExtractedRelation:
    subject: str
    predicate: str
    object: str


SERVICE_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z0-9_-]+(?:Service|API|Gateway|Worker))\b"
)
ENTITY_CAP_PATTERN = re.compile(r"\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)*)\b")
DEPENDS_PATTERN = re.compile(
    r"(\w[\w-]*)\s+(?:depends on|uses|calls|connects to)\s+(\w[\w-]*)",
    re.IGNORECASE,
)


def extract_entities(text: str) -> list[ExtractedEntity]:
    entities: dict[str, ExtractedEntity] = {}

    for match in SERVICE_PATTERN.finditer(text):
        name = match.group(1)
        entities[name.lower()] = ExtractedEntity(
            name=name,
            entity_type="Service",
            canonical_id=f"service:{name.lower()}",
        )

    for match in ENTITY_CAP_PATTERN.finditer(text):
        name = match.group(1).strip()
        if len(name) < 4 or name.lower() in {"the second brain", "working memory"}:
            continue
        key = name.lower().replace(" ", "_")
        if key not in entities:
            entities[key] = ExtractedEntity(
                name=name,
                entity_type="Concept",
                canonical_id=f"concept:{key}",
            )

    return list(entities.values())


def extract_relations(text: str, entities: list[ExtractedEntity]) -> list[ExtractedRelation]:
    relations: list[ExtractedRelation] = []
    entity_names = {e.name.lower() for e in entities}

    for match in DEPENDS_PATTERN.finditer(text):
        subj, obj = match.group(1), match.group(2)
        if subj.lower() in entity_names or obj.lower() in entity_names:
            relations.append(
                ExtractedRelation(subject=subj, predicate="DEPENDS_ON", object=obj)
            )

    return relations


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Heading-aware semantic chunking."""
    sections = re.split(r"\n(?=#{1,3}\s)", text)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
            continue
        start = 0
        while start < len(section):
            end = min(len(section), start + max_chars)
            chunks.append(section[start:end].strip())
            if end >= len(section):
                break
            start = end - overlap
    return chunks or [text[:max_chars]]
