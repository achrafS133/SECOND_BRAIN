from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AblationProfile:
    """Toggle CogOS subsystems for paper ablation studies."""

    name: str
    use_working_memory: bool = True
    use_hybrid_scoring: bool = True
    use_graph_edges: bool = True
    use_community_summary: bool = True
    use_critic: bool = True
    vector_only: bool = False


FLAT_RAG = AblationProfile(
    name="flat_rag",
    use_working_memory=False,
    use_hybrid_scoring=False,
    use_graph_edges=False,
    use_community_summary=False,
    use_critic=False,
    vector_only=True,
)

GRAPH_ONLY = AblationProfile(
    name="graph_only",
    use_working_memory=False,
    use_hybrid_scoring=False,
    use_graph_edges=True,
    use_community_summary=False,
    use_critic=False,
    vector_only=False,
)

TIERED_MEMORY = AblationProfile(
    name="tiered_memory",
    use_working_memory=True,
    use_hybrid_scoring=True,
    use_graph_edges=True,
    use_community_summary=True,
    use_critic=False,
    vector_only=False,
)

FULL_COGOS = AblationProfile(
    name="full_cogos",
    use_working_memory=True,
    use_hybrid_scoring=True,
    use_graph_edges=True,
    use_community_summary=True,
    use_critic=True,
    vector_only=False,
)

ALL_PROFILES = [FLAT_RAG, GRAPH_ONLY, TIERED_MEMORY, FULL_COGOS]
