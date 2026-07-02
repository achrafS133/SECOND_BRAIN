# Faust stream workers

Async Kafka stream processing is implemented in the main package:

- **Documents:** `second-brain-pipeline` → consumes `raw.documents` → Neo4j M₂
- **IoT:** `second-brain-pipeline iot` → consumes `stream.iot` → M₀ + anomaly agent

Docker Compose (`--profile app`):

```powershell
docker compose -f infra/docker-compose.yml --profile app up -d pipeline pipeline-iot
```

See `src/second_brain/ingestion/kafka/pipeline.py`.
