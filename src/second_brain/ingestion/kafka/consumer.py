from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from second_brain.config import get_settings
from second_brain.ingestion.kafka.topics import TOPICS

logger = logging.getLogger(__name__)


async def consume_raw_documents() -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        TOPICS.RAW_DOCUMENTS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.kafka_consumer_group}-documents",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Consuming topic %s", TOPICS.RAW_DOCUMENTS)
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            logger.info("Received document event: %s", payload.get("uri", "unknown"))
    finally:
        await consumer.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(consume_raw_documents())


if __name__ == "__main__":
    main()
