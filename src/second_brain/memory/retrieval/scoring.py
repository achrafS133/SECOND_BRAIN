from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone


def _normalize_dt(dt: datetime) -> datetime:
    """Compare naive and aware datetimes by coercing both to UTC-naive."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass
class MemoryUnit:
    id: str
    text: str
    embedding: list[float] | None = None
    timestamp: datetime | None = None
    importance: float = 0.5
    graph_proximity: float = 0.0
    source_uri: str | None = None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def recency_score(timestamp: datetime | None, now: datetime, tau_hours: float = 72.0) -> float:
    if timestamp is None:
        return 0.5
    timestamp = _normalize_dt(timestamp)
    now = _normalize_dt(now)
    delta_hours = max(0.0, (now - timestamp).total_seconds() / 3600.0)
    return math.exp(-delta_hours / tau_hours)


def graph_proximity_score(query: str, text: str, entity_names: list[str] | None = None) -> float:
    """Psi_G proxy: overlap between query tokens and entity names / text."""
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not query_tokens:
        return 0.0
    targets = set(re.findall(r"[a-z0-9]+", text.lower()))
    if entity_names:
        for name in entity_names:
            targets.update(re.findall(r"[a-z0-9]+", name.lower()))
    overlap = len(query_tokens & targets)
    return min(1.0, overlap / max(1, len(query_tokens)))


def retrieval_score(
    unit: MemoryUnit,
    query: str,
    query_embedding: list[float],
    now: datetime | None = None,
    *,
    alpha: float = 0.45,
    beta: float = 0.20,
    gamma: float = 0.15,
    delta: float = 0.20,
    tau_hours: float = 72.0,
    entity_names: list[str] | None = None,
) -> float:
    """
    R(m | q, t) = alpha*sim + beta*recency + gamma*importance + delta*Psi_G
    """
    now = now or datetime.utcnow()
    sim = cosine_similarity(query_embedding, unit.embedding or [])
    if unit.embedding is None:
        sim = graph_proximity_score(query, unit.text, entity_names)
    rec = recency_score(unit.timestamp, now, tau_hours)
    imp = max(0.0, min(1.0, unit.importance))
    psi = max(unit.graph_proximity, graph_proximity_score(query, unit.text, entity_names))
    return alpha * sim + beta * rec + gamma * imp + delta * psi


def rank_units(
    units: list[MemoryUnit],
    query: str,
    query_embedding: list[float],
    top_k: int = 8,
    **kwargs,
) -> list[tuple[MemoryUnit, float]]:
    scored = [(u, retrieval_score(u, query, query_embedding, **kwargs)) for u in units]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]
