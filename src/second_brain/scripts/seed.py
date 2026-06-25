"""Seed The Second Brain with sample enterprise + IoT knowledge."""

from __future__ import annotations

import asyncio
import logging

from second_brain.config import get_settings
from second_brain.schemas import IngestDocumentRequest, IoTTelemetryEvent
from second_brain.services.container import ServiceContainer

SAMPLE_DOCS = [
    IngestDocumentRequest(
        uri="doc://architecture/memory",
        title="Memory Tier Model",
        content=(
            "## Memory Tiers\n"
            "The Second Brain uses M0 working memory for IoT streams, "
            "M1 short-term in-context memory, and M2 long-term Neo4j graph memory.\n"
            "CheckoutService depends on PaymentGateway for transaction authorization."
        ),
    ),
    IngestDocumentRequest(
        uri="doc://runbook/latency",
        title="Checkout Latency Runbook",
        content=(
            "## Incident Response\n"
            "If checkout latency spikes, inspect PaymentGateway upstream dependencies "
            "and recent deploy events in BillingService."
        ),
    ),
]


async def seed() -> None:
    settings = get_settings()
    container = ServiceContainer(settings)
    await container.startup()

    for doc in SAMPLE_DOCS:
        ids = await container.ingest_document(doc)
        print(f"Ingested {doc.title}: {len(ids)} chunks")

    for value in [22.0, 22.5, 23.0, 22.8, 23.1, 22.9, 23.0, 45.0]:
        event = IoTTelemetryEvent(
            device_id="hvac-zone-a-1",
            zone_id="zone-a",
            metric="temperature",
            value=value,
        )
        result = await container.process_iot(event)
        if result.get("anomaly_detected"):
            print("Anomaly handled:", result.get("summary"))

    await container.shutdown()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
