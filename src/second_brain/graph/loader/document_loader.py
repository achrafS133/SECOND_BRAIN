from __future__ import annotations

from uuid import uuid4

from second_brain.ingestion.extraction.entities import (
    chunk_text,
    extract_entities,
    extract_relations,
)
from second_brain.memory.retrieval.embeddings import EmbeddingService
from second_brain.memory.tiers.long_term import LongTermMemory
from second_brain.schemas import IngestDocumentRequest


class DocumentLoader:
    def __init__(self, long_term: LongTermMemory, embeddings: EmbeddingService) -> None:
        self.long_term = long_term
        self.embeddings = embeddings

    async def ingest(self, doc: IngestDocumentRequest) -> list[str]:
        chunks = chunk_text(doc.content)
        entities = extract_entities(doc.content)
        relations = extract_relations(doc.content, entities)
        chunk_ids: list[str] = []

        for index, chunk in enumerate(chunks):
            chunk_id = f"{doc.uri}#chunk-{index}-{uuid4().hex[:6]}"
            vector = self.embeddings.embed_query(chunk)
            self.long_term.upsert_document_chunk(
                uri=doc.uri,
                title=doc.title,
                chunk_id=chunk_id,
                text=chunk,
                embedding=vector,
                metadata={**doc.metadata, "chunk_index": index},
            )
            if entities:
                self.long_term.link_chunk_entities(chunk_id, [e.name for e in entities[:20]])
            chunk_ids.append(chunk_id)

        for entity in entities:
            self.long_term.upsert_entity(entity.name, entity.entity_type, entity.canonical_id)

        for rel in relations:
            self.long_term.upsert_relation(rel.subject, rel.predicate, rel.object)

        return chunk_ids
