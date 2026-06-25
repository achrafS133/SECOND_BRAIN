from __future__ import annotations

import logging
from collections import defaultdict

from second_brain.memory.tiers.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class CommunitySummaryService:
    """Lightweight GraphRAG-style community summaries over entity clusters."""

    def __init__(self, long_term: LongTermMemory) -> None:
        self.long_term = long_term
        self._cache: dict[str, str] = {}

    def build_summaries(self) -> dict[str, str]:
        entities = self.long_term.list_entities(limit=200)
        if not entities:
            return {}

        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in self.long_term.list_entity_edges(limit=500):
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])

        visited: set[str] = set()
        communities: list[list[str]] = []

        for entity in entities:
            name = entity["name"]
            if name in visited:
                continue
            stack = [name]
            cluster: list[str] = []
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                cluster.append(node)
                stack.extend(adjacency.get(node, []))
            if cluster:
                communities.append(sorted(cluster))

        summaries: dict[str, str] = {}
        for idx, cluster in enumerate(communities):
            community_id = f"community-{idx}"
            summary = (
                f"Community {idx} connects entities: {', '.join(cluster[:12])}"
                f"{'...' if len(cluster) > 12 else ''}."
            )
            summaries[community_id] = summary
            self.long_term.store_community_summary(community_id, summary, cluster)

        self._cache = summaries
        logger.info("Built %s community summaries", len(summaries))
        return summaries

    def lookup_for_query(self, query: str) -> str | None:
        if not self._cache:
            self._cache = self.long_term.get_community_summaries()

        query_lower = query.lower()
        for community_id, summary in self._cache.items():
            tokens = community_id.lower().split("-")
            if any(token in query_lower for token in tokens if len(token) > 3):
                return summary
            if any(part in summary.lower() for part in query_lower.split() if len(part) > 4):
                return summary
        return None
