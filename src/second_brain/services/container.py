from __future__ import annotations

import logging

from aiokafka import AIOKafkaProducer

from second_brain.agents.graph.cogos import CogOSGraph
from second_brain.agents.roles.stream_observer import StreamObserver
from second_brain.config import Settings
from second_brain.graph.community.summaries import CommunitySummaryService
from second_brain.graph.loader.document_loader import DocumentLoader
from second_brain.ingestion.kafka.topics import TOPICS
from second_brain.memory.consolidation.reflection import ReflectionEngine
from second_brain.memory.manager import MemoryManager
from second_brain.memory.retrieval.embeddings import EmbeddingService
from second_brain.memory.tiers.long_term import LongTermMemory
from second_brain.memory.tiers.short_term import ShortTermMemory
from second_brain.memory.tiers.working import WorkingMemory
from second_brain.schemas import (
    ActionDecision,
    ActionStatus,
    IngestDocumentRequest,
    IoTTelemetryEvent,
    MemoryObservation,
    ObservationKind,
    PendingAction,
    ProposedAction,
    TaskType,
)
from second_brain.services.action_orchestrator import ActionOrchestrator
from second_brain.services.action_service import ActionStore, IoTControlPlane

logger = logging.getLogger(__name__)


class ServiceContainer:
    def __init__(self, settings: Settings, ablation=None) -> None:
        from second_brain.eval.ablation.config import FULL_COGOS

        self.settings = settings
        self.ablation = ablation or FULL_COGOS
        self.working = WorkingMemory(settings)
        self.short_term = ShortTermMemory(token_budget=settings.context_token_budget)
        self.long_term = LongTermMemory(settings)
        self.embeddings = EmbeddingService(settings)
        self.memory = MemoryManager(
            self.working, self.short_term, self.long_term, ablation=self.ablation
        )
        self.loader = DocumentLoader(self.long_term, self.embeddings)
        self.stream_observer = StreamObserver(sigma=3.0)
        self.reflection = ReflectionEngine()
        self.communities = CommunitySummaryService(self.long_term)
        self.action_store = ActionStore(self.working)
        self.control_plane = IoTControlPlane(settings)
        self.actions = ActionOrchestrator(settings, self.action_store, self.control_plane)
        self.cogos = CogOSGraph(
            settings, self.memory, self.embeddings, ablation=self.ablation
        )
        self._session_observations: dict[str, list[MemoryObservation]] = {}
        self._kafka: AIOKafkaProducer | None = None
        self._mqtt_bridge = None

    async def startup(self) -> None:
        await self.working.connect()
        self.long_term.connect()
        try:
            producer = AIOKafkaProducer(
                bootstrap_servers=self.settings.kafka_bootstrap_servers,
            )
            await producer.start()
            self._kafka = producer
            logger.info("Kafka producer connected")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Kafka unavailable: %s", exc)
            self._kafka = None

        if self.settings.mqtt_enabled:
            try:
                from second_brain.ingestion.mqtt.bridge import MqttTelemetryBridge

                self._mqtt_bridge = MqttTelemetryBridge(self.settings, self)
                await self._mqtt_bridge.start()
            except Exception as exc:  # noqa: BLE001
                logger.warning("MQTT bridge unavailable: %s", exc)
                self._mqtt_bridge = None

    async def shutdown(self) -> None:
        if self._mqtt_bridge:
            await self._mqtt_bridge.stop()
        self.control_plane.close()
        await self.working.close()
        self.long_term.close()
        if self._kafka:
            await self._kafka.stop()

    async def health(self) -> dict:
        try:
            await self.working.set("health", "check", {"ok": True}, ttl_seconds=10)
            redis_ok = True
        except Exception:  # noqa: BLE001
            redis_ok = False
        pending = await self.actions.list_pending()
        return {
            "redis": redis_ok,
            "neo4j": self.long_term._driver is not None,
            "kafka": self._kafka is not None,
            "pending_actions": len(pending),
            "iot_dry_run": self.settings.iot_dry_run,
            "mqtt_enabled": self.settings.mqtt_enabled,
            "ablation": self.ablation.name,
        }

    async def ingest_document(self, body: IngestDocumentRequest) -> list[str]:
        chunk_ids = await self.loader.ingest(body)
        if self._kafka:
            await self._kafka.send_and_wait(
                TOPICS.RAW_DOCUMENTS,
                value=body.model_dump_json().encode(),
            )
        return chunk_ids

    async def build_communities(self) -> dict:
        return self.communities.build_summaries()

    async def process_iot(self, event: IoTTelemetryEvent) -> dict:
        observation = self.stream_observer.observe(event)
        await self.working.update_iot_window(event.device_id, observation["stats"])

        result = {
            "stats": observation["stats"],
            "anomaly_detected": observation["anomaly_detected"],
            "summary": observation["summary"],
        }

        if observation["anomaly_detected"]:
            session_id = f"iot-{event.zone_id}"
            await self.working.pin(session_id, observation["pin_payload"])

            analysis = await self.cogos.run(
                query=observation["summary"],
                session_id=session_id,
                task_type=TaskType.ANOMALY,
            )
            result["agent_response"] = analysis.answer
            result["critic_verdict"] = analysis.critic_verdict.value

            action = await self.actions.propose_from_anomaly(
                device_id=event.device_id,
                zone_id=event.zone_id,
                metric=event.metric,
                stats=observation["stats"],
                session_id=session_id,
            )
            result["action"] = action.model_dump(mode="json")
            result["pending_action_id"] = (
                action.id if action.status == ActionStatus.PENDING else None
            )

            if action.status == ActionStatus.EXECUTED:
                result["execution_result"] = action.execution_result

        if self._kafka:
            await self._kafka.send_and_wait(
                TOPICS.STREAM_IOT,
                value=event.model_dump_json().encode(),
            )

        return result

    async def propose_action(self, proposed: ProposedAction, session_id: str) -> PendingAction:
        return await self.actions.propose(proposed, session_id)

    async def approve_action(self, action_id: str, decision: ActionDecision) -> PendingAction:
        return await self.actions.approve(action_id, decision)

    async def list_pending_actions(self) -> list[PendingAction]:
        return await self.actions.list_pending()

    async def record_session_observation(
        self, session_id: str, text: str, importance: float = 0.6
    ) -> None:
        obs = MemoryObservation(
            text=text,
            kind=ObservationKind.OBSERVATION,
            importance=importance,
        )
        self._session_observations.setdefault(session_id, []).append(obs)
        await self.memory.promote_observation(obs)

    async def consolidate_session(self, session_id: str) -> dict:
        observations = self._session_observations.get(session_id, [])
        if len(observations) < 2:
            return {"status": "skipped", "reason": "need at least 2 observations"}
        reflection = self.reflection.consolidate(observations)
        self.long_term.store_reflection(reflection)
        self._session_observations[session_id] = []
        return {
            "status": "consolidated",
            "reflection_id": reflection.id,
            "importance": reflection.importance,
        }
