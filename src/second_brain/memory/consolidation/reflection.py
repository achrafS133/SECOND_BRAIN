from __future__ import annotations

from uuid import uuid4

from second_brain.schemas import MemoryObservation, ObservationKind


class ReflectionEngine:
    """Episodic cluster -> semantic reflection (Generative Agents style)."""

    def consolidate(self, observations: list[MemoryObservation], max_chars: int = 500) -> MemoryObservation:
        lines = [f"- {o.text}" for o in observations[:10]]
        body = "\n".join(lines)
        reflection_text = f"Reflection over {len(observations)} observations:\n{body[:max_chars]}"
        avg_importance = sum(o.importance for o in observations) / max(1, len(observations))
        return MemoryObservation(
            id=str(uuid4()),
            text=reflection_text,
            kind=ObservationKind.REFLECTION,
            importance=min(1.0, avg_importance + 0.15),
            metadata={"source_count": len(observations)},
        )
