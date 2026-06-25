from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from neo4j import Driver, GraphDatabase

from second_brain.config import Settings
from second_brain.eval.ablation.config import FULL_COGOS, AblationProfile
from second_brain.memory.retrieval.scoring import MemoryUnit, cosine_similarity, rank_units
from second_brain.schemas import EvidencePackage, GraphEdge, GraphNode, MemoryObservation

logger = logging.getLogger(__name__)


class LongTermMemory:
    """M2 — Neo4j graph + hybrid vector retrieval."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._driver: Driver | None = None
        self._local_chunks: list[dict[str, Any]] = []
        self._local_entities: list[dict[str, str]] = []

    def connect(self) -> None:
        try:
            self._driver = GraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            )
            self._driver.verify_connectivity()
            logger.info("Long-term memory connected to Neo4j")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j unavailable, using in-memory M2 fallback: %s", exc)
            self._driver = None

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def upsert_document_chunk(
        self,
        uri: str,
        title: str,
        chunk_id: str,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        now = datetime.utcnow()
        record = {
            "uri": uri,
            "title": title,
            "chunk_id": chunk_id,
            "text": text,
            "embedding": embedding,
            "metadata": metadata,
            "importance": metadata.get("importance", 0.5),
            "timestamp": now,
        }
        if not self._driver:
            self._local_chunks = [c for c in self._local_chunks if c["chunk_id"] != chunk_id]
            self._local_chunks.append(record)
            return

        query = """
        MERGE (d:Document {uri: $uri})
        ON CREATE SET d.title = $title, d.created_at = datetime()
        ON MATCH SET d.title = $title, d.updated_at = datetime()
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.text = $text,
            c.embedding = $embedding,
            c.metadata_json = $metadata_json,
            c.importance = $importance,
            c.updated_at = datetime()
        MERGE (d)-[:CONTAINS]->(c)
        """
        with self._driver.session() as session:
            session.run(
                query,
                uri=uri,
                title=title,
                chunk_id=chunk_id,
                text=text,
                embedding=embedding,
                metadata_json=json.dumps(metadata),
                importance=metadata.get("importance", 0.5),
            )

    def upsert_entity(self, name: str, entity_type: str, canonical_id: str) -> None:
        if not self._driver:
            self._local_entities = [
                e for e in self._local_entities if e["canonical_id"] != canonical_id
            ]
            self._local_entities.append(
                {"name": name, "type": entity_type, "canonical_id": canonical_id}
            )
            return

        query = """
        MERGE (e:Entity {canonical_id: $canonical_id})
        SET e.name = $name, e.type = $entity_type
        """
        with self._driver.session() as session:
            session.run(query, name=name, entity_type=entity_type, canonical_id=canonical_id)

    def upsert_relation(self, subject: str, predicate: str, object_name: str) -> None:
        if not self._driver:
            return
        query = """
        MERGE (a:Entity {name: $subject})
        MERGE (b:Entity {name: $object_name})
        MERGE (a)-[r:RELATES_TO {predicate: $predicate}]->(b)
        """
        with self._driver.session() as session:
            session.run(query, subject=subject, predicate=predicate, object_name=object_name)

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 8,
        profile: AblationProfile | None = None,
    ) -> EvidencePackage:
        profile = profile or FULL_COGOS
        units = self._fetch_candidate_units(
            query, query_embedding, max(top_k * 3, 12), profile=profile
        )
        if not units:
            return EvidencePackage()

        if profile.vector_only:
            ranked = [
                (u, cosine_similarity(query_embedding, u.embedding or []))
                for u in units
            ]
            ranked.sort(key=lambda x: -x[1])
            ranked = ranked[:top_k]
        elif not profile.use_hybrid_scoring:
            ranked = [(u, u.graph_proximity) for u in units[:top_k]]
        else:
            entity_names = [e["name"] for e in self._local_entities] if not self._driver else []
            ranked = rank_units(units, query, query_embedding, top_k=top_k, entity_names=entity_names)

        nodes = [
            GraphNode(
                id=unit.id,
                label="Chunk",
                properties={
                    "text": unit.text,
                    "score": round(score, 4),
                    "importance": unit.importance,
                },
            )
            for unit, score in ranked
        ]
        provenance = [u.source_uri for u, _ in ranked if u.source_uri]
        edges = self._fetch_related_edges([n.id for n in nodes]) if profile.use_graph_edges else []

        return EvidencePackage(
            nodes=nodes,
            edges=edges,
            provenance=list(dict.fromkeys(provenance)),
            retrieval_score=ranked[0][1] if ranked else 0.0,
        )

    def _fetch_candidate_units(
        self,
        query: str,
        query_embedding: list[float],
        limit: int,
        profile: AblationProfile | None = None,
    ) -> list[MemoryUnit]:
        profile = profile or FULL_COGOS
        if not self._driver:
            return [
                MemoryUnit(
                    id=c["chunk_id"],
                    text=c["text"],
                    embedding=c.get("embedding"),
                    timestamp=c.get("timestamp"),
                    importance=c.get("importance", 0.5),
                    source_uri=c.get("uri"),
                )
                for c in self._local_chunks
            ]

        if not profile.vector_only and not profile.use_hybrid_scoring:
            return self._text_units(query, limit)

        vector_cypher = """
        CALL db.index.vector.queryNodes('chunk_vector', $limit, $embedding)
        YIELD node, score AS vector_score
        OPTIONAL MATCH (d:Document)-[:CONTAINS]->(node)
        RETURN node.chunk_id AS id, node.text AS text, node.embedding AS embedding,
               node.importance AS importance, node.updated_at AS updated_at,
               vector_score, d.uri AS source_uri
        LIMIT $limit
        """
        try:
            with self._driver.session() as session:
                rows = list(
                    session.run(
                        vector_cypher,
                        embedding=query_embedding,
                        limit=limit,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector search failed, using text fallback: %s", exc)
            return self._text_units(query, limit)

        units: list[MemoryUnit] = []
        for row in rows:
            ts = row["updated_at"]
            timestamp = ts.to_native() if hasattr(ts, "to_native") else None
            units.append(
                MemoryUnit(
                    id=row["id"],
                    text=row["text"],
                    embedding=list(row["embedding"]) if row["embedding"] else None,
                    timestamp=timestamp,
                    importance=float(row["importance"] or 0.5),
                    graph_proximity=float(row["vector_score"] or 0.0),
                    source_uri=row["source_uri"],
                )
            )
        return units

    def _text_units(self, query: str, limit: int) -> list[MemoryUnit]:
        term = query.split()[0] if query.split() else query
        cypher = """
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS toLower($term)
        OPTIONAL MATCH (d:Document)-[:CONTAINS]->(c)
        RETURN c.chunk_id AS id, c.text AS text, c.importance AS importance,
               d.uri AS source_uri
        LIMIT $limit
        """
        units: list[MemoryUnit] = []
        with self._driver.session() as session:
            for row in session.run(cypher, term=term, limit=limit):
                units.append(
                    MemoryUnit(
                        id=row["id"],
                        text=row["text"],
                        importance=float(row["importance"] or 0.5),
                        source_uri=row["source_uri"],
                    )
                )
        return units

    def _fetch_related_edges(self, chunk_ids: list[str]) -> list[GraphEdge]:
        if not self._driver or not chunk_ids:
            return []
        cypher = """
        MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)-[r:RELATES_TO]->(e2:Entity)
        WHERE c.chunk_id IN $chunk_ids
        RETURN e.name AS source, e2.name AS target, r.predicate AS predicate
        LIMIT 20
        """
        edges: list[GraphEdge] = []
        with self._driver.session() as session:
            for row in session.run(cypher, chunk_ids=chunk_ids):
                edges.append(
                    GraphEdge(
                        source_id=row["source"],
                        target_id=row["target"],
                        type=row["predicate"] or "RELATES_TO",
                    )
                )
        return edges

    def store_observation(self, observation: MemoryObservation) -> None:
        if not self._driver:
            return
        query = """
        CREATE (o:AgentObservation {
            id: $id,
            text: $text,
            timestamp: datetime($timestamp),
            kind: $kind,
            importance: $importance
        })
        """
        with self._driver.session() as session:
            session.run(
                query,
                id=observation.id,
                text=observation.text,
                timestamp=observation.timestamp.isoformat(),
                kind=observation.kind.value,
                importance=observation.importance,
            )

    def store_reflection(self, reflection: MemoryObservation) -> None:
        self.store_observation(reflection)

    def link_chunk_entities(self, chunk_id: str, entity_names: list[str]) -> None:
        if not self._driver:
            return
        query = """
        MATCH (c:Chunk {chunk_id: $chunk_id})
        UNWIND $entity_names AS name
        MERGE (e:Entity {name: name})
        MERGE (c)-[:MENTIONS]->(e)
        """
        with self._driver.session() as session:
            session.run(query, chunk_id=chunk_id, entity_names=entity_names)

    def list_entities(self, limit: int = 100) -> list[dict]:
        if not self._driver:
            return [{"name": e["name"], "type": e["type"]} for e in self._local_entities[:limit]]
        query = "MATCH (e:Entity) RETURN e.name AS name, e.type AS type LIMIT $limit"
        with self._driver.session() as session:
            return [dict(row) for row in session.run(query, limit=limit)]

    def list_entity_edges(self, limit: int = 200) -> list[dict]:
        if not self._driver:
            return []
        query = """
        MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
        RETURN a.name AS source, b.name AS target, r.predicate AS predicate
        LIMIT $limit
        """
        with self._driver.session() as session:
            return [dict(row) for row in session.run(query, limit=limit)]

    def store_community_summary(
        self, community_id: str, summary: str, entity_names: list[str]
    ) -> None:
        if not self._driver:
            return
        query = """
        MERGE (c:Community {community_id: $community_id})
        SET c.summary = $summary, c.updated_at = datetime()
        WITH c
        UNWIND $entity_names AS name
        MERGE (e:Entity {name: name})
        MERGE (e)-[:IN_COMMUNITY]->(c)
        """
        with self._driver.session() as session:
            session.run(
                query,
                community_id=community_id,
                summary=summary,
                entity_names=entity_names,
            )

    def get_community_summaries(self) -> dict[str, str]:
        if not self._driver:
            return {}
        query = "MATCH (c:Community) RETURN c.community_id AS id, c.summary AS summary"
        with self._driver.session() as session:
            return {row["id"]: row["summary"] for row in session.run(query)}

    def lookup_community_summary(self, query: str) -> str | None:
        summaries = self.get_community_summaries()
        query_lower = query.lower()
        for summary in summaries.values():
            if any(token in summary.lower() for token in query_lower.split() if len(token) > 4):
                return summary
        return None
