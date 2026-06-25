from __future__ import annotations

from second_brain.schemas import ContextBundle, EvidencePackage, MemoryObservation


class ShortTermMemory:
    """M1 — in-context window management with token budget."""

    CORE_PERSONA = (
        "You are The Second Brain, a cognitive operating system. "
        "Ground answers in retrieved evidence. Be precise and auditable."
    )

    def __init__(self, token_budget: int = 8192) -> None:
        self.token_budget = token_budget
        self._core_blocks: list[str] = [self.CORE_PERSONA]
        self._dialogue: list[str] = []

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def append_turn(self, role: str, content: str) -> None:
        self._dialogue.append(f"{role.upper()}: {content}")

    def add_core_block(self, block: str) -> None:
        if block not in self._core_blocks:
            self._core_blocks.append(block)

    def assemble(
        self,
        evidence: EvidencePackage | None = None,
        pinned: dict | None = None,
    ) -> ContextBundle:
        pinned = pinned or {}
        parts: list[tuple[str, int, float]] = []

        for block in self._core_blocks:
            parts.append((block, self.estimate_tokens(block), 10.0))

        if pinned:
            pinned_text = f"PINNED_WORKING_STATE: {pinned}"
            parts.append((pinned_text, self.estimate_tokens(pinned_text), 9.0))

        if evidence and evidence.nodes:
            evidence_lines = ["RETRIEVED_EVIDENCE:"]
            for node in evidence.nodes[:10]:
                evidence_lines.append(f"- [{node.label}] {node.properties.get('text', node.id)}")
            if evidence.community_summary:
                evidence_lines.append(f"COMMUNITY: {evidence.community_summary}")
            evidence_text = "\n".join(evidence_lines)
            parts.append((evidence_text, self.estimate_tokens(evidence_text), 8.0))

        for turn in reversed(self._dialogue):
            tokens = self.estimate_tokens(turn)
            parts.append((turn, tokens, 1.0))

        selected: list[str] = []
        used = 0
        for text, tokens, _priority in sorted(parts, key=lambda x: -x[2]):
            if used + tokens > self.token_budget:
                continue
            selected.append(text)
            used += tokens

        return ContextBundle(
            core_blocks=list(self._core_blocks),
            dialogue_turns=[t for t in self._dialogue if t in selected or not selected],
            pinned_working_state=pinned,
            retrieved_evidence=evidence,
            estimated_tokens=used,
        )

    def queue_promotion(self, observation: MemoryObservation) -> bool:
        return observation.importance >= 0.7
