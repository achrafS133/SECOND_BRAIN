// Neo4j schema bootstrap for The Second Brain (M2 long-term memory)

CREATE CONSTRAINT document_uri IF NOT EXISTS
FOR (d:Document) REQUIRE d.uri IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;

CREATE CONSTRAINT entity_canonical IF NOT EXISTS
FOR (e:Entity) REQUIRE e.canonical_id IS UNIQUE;

CREATE CONSTRAINT service_name IF NOT EXISTS
FOR (s:Service) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT device_id IF NOT EXISTS
FOR (d:IoTDevice) REQUIRE d.device_id IS UNIQUE;

CREATE INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding);

CREATE INDEX entity_name IF NOT EXISTS
FOR (e:Entity) ON (e.name);

CREATE INDEX observation_timestamp IF NOT EXISTS
FOR (o:AgentObservation) ON (o.timestamp);

CREATE VECTOR INDEX chunk_vector IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}};
