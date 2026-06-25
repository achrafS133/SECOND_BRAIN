from __future__ import annotations

from second_brain.eval.ablation.config import FULL_COGOS, AblationProfile
from second_brain.memory.tiers.long_term import LongTermMemory
from second_brain.memory.tiers.short_term import ShortTermMemory
from second_brain.memory.tiers.working import WorkingMemory
from second_brain.schemas import ContextBundle, EvidencePackage, MemoryObservation


class MemoryManager:
    """Coordinates M0, M1, and M2 memory tiers."""

    def __init__(
        self,
        working: WorkingMemory,
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
        ablation: AblationProfile | None = None,
    ) -> None:
        self.working = working
        self.short_term = short_term
        self.long_term = long_term
        self.ablation = ablation or FULL_COGOS

    async def assemble_context(
        self,
        session_id: str,
        query: str,
        query_embedding: list[float],
        top_k: int = 8,
    ) -> ContextBundle:
        pinned = (
            await self.working.get_pinned(session_id)
            if self.ablation.use_working_memory
            else {}
        )
        evidence = self.long_term.hybrid_search(
            query, query_embedding, top_k=top_k, profile=self.ablation
        )
        if self.ablation.use_community_summary:
            community = self.long_term.lookup_community_summary(query)
            if community and evidence:
                evidence.community_summary = community
            elif community and not evidence.nodes:
                evidence = EvidencePackage(community_summary=community)
        return self.short_term.assemble(evidence=evidence, pinned=pinned)

    async def record_turn(self, role: str, content: str) -> None:
        self.short_term.append_turn(role, content)

    async def promote_observation(self, observation: MemoryObservation) -> None:
        if self.short_term.queue_promotion(observation):
            self.long_term.store_observation(observation)

    def format_context_for_llm(self, bundle: ContextBundle) -> str:
        sections = []
        sections.extend(bundle.core_blocks)
        if bundle.pinned_working_state:
            sections.append(f"Working state: {bundle.pinned_working_state}")
        if bundle.retrieved_evidence and bundle.retrieved_evidence.nodes:
            lines = ["Evidence:"]
            for node in bundle.retrieved_evidence.nodes:
                lines.append(f"- {node.properties.get('text', node.id)}")
            if bundle.retrieved_evidence.community_summary:
                lines.append(f"Community: {bundle.retrieved_evidence.community_summary}")
            sections.append("\n".join(lines))
        elif bundle.retrieved_evidence and bundle.retrieved_evidence.community_summary:
            sections.append(f"Community: {bundle.retrieved_evidence.community_summary}")
        sections.extend(bundle.dialogue_turns[-6:])
        return "\n\n".join(sections)
