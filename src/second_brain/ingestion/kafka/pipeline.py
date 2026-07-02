from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from second_brain.config import get_settings
from second_brain.ingestion.kafka.topics import TOPICS
from second_brain.schemas import IngestDocumentRequest, IoTTelemetryEvent

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
            chunk_ids = await container.ingest_from_kafka(doc)
            logger.info("Pipeline ingested %s -> %s chunks", doc.uri, len(chunk_ids))
    finally:
        await consumer.stop()
        await container.shutdown()


async def run_iot_pipeline() -> None:
    settings = get_settings()
    from second_brain.services.container import ServiceContainer

    container = ServiceContainer(settings)
    await container.startup()

    consumer = AIOKafkaConsumer(
        TOPICS.STREAM_IOT,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.kafka_consumer_group}-iot",
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info("IoT pipeline listening on %s", TOPICS.STREAM_IOT)

    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            event = IoTTelemetryEvent(**payload)
            result = await container.process_iot(event, publish_kafka=False)
            if result.get("anomaly_detected"):
                logger.warning(
                    "IoT anomaly %s/%s pending=%s",
                    event.device_id,
                    event.metric,
                    result.get("pending_action_id"),
                )
            else:
                logger.info(
                    "IoT nominal %s mean=%.2f",
                    event.device_id,
                    result["stats"]["mean"],
                )
    finally:
        await consumer.stop()
        await container.shutdown()


def main() -> None:
    import sys

    logging.basicConfig(level=logging.INFO)
    mode = sys.argv[1] if len(sys.argv) > 1 else "documents"
    if mode == "iot":
        asyncio.run(run_iot_pipeline())
    else:
        asyncio.run(run_document_pipeline())


if __name__ == "__main__":
    main()
