from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from second_brain.config import get_settings
from second_brain.ingestion.kafka.topics import TOPICS
from second_brain.schemas import IngestDocumentRequest

logger = logging.getLogger(__name__)


async def run_document_pipeline() -> None:
    settings = get_settings()
    from second_brain.services.container import ServiceContainer

    container = ServiceContainer(settings)
    await container.startup()

    consumer = AIOKafkaConsumer(
        TOPICS.RAW_DOCUMENTS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.kafka_consumer_group}-pipeline",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Document pipeline listening on %s", TOPICS.RAW_DOCUMENTS)

    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            doc = IngestDocumentRequest(**payload)
            chunk_ids = await container.ingest_document(doc)
            logger.info("Pipeline ingested %s -> %s chunks", doc.uri, len(chunk_ids))
    finally:
        await consumer.stop()
        await container.shutdown()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_document_pipeline())


if __name__ == "__main__":
    main()
