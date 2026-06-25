from __future__ import annotations

from second_brain.schemas import CriticVerdict, EvidencePackage


def evaluate_answer(
    draft: str,
    evidence: EvidencePackage | None,
    task_type: str = "qa",
) -> tuple[CriticVerdict, str]:
    """Lightweight critic: checks grounding and basic policy."""
    if not draft.strip():
        return CriticVerdict.REJECT, "Empty draft answer."

    if task_type == "action" and "override safety" in draft.lower():
        return CriticVerdict.REJECT, "Policy violation: unsafe action language detected."

    if evidence and evidence.nodes:
        evidence_text = " ".join(
            str(node.properties.get("text", "")) for node in evidence.nodes
        ).lower()
        keywords = [w for w in draft.lower().split() if len(w) > 5][:5]
        overlap = sum(1 for kw in keywords if kw in evidence_text)
        if overlap == 0 and len(keywords) > 2:
            return CriticVerdict.REVISE, "Low evidence overlap — tighten grounding to retrieved nodes."
        return CriticVerdict.ACCEPT, "Answer aligns with retrieved evidence."

    if "I don't know" in draft or "no long-term evidence" in draft.lower():
        return CriticVerdict.ACCEPT, "Honest uncertainty accepted."

    return CriticVerdict.REVISE, "No evidence retrieved — ingest knowledge or refine query."
