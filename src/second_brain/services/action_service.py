from __future__ import annotations

import logging
from typing import Any

from second_brain.config import Settings
from second_brain.memory.tiers.working import WorkingMemory
from second_brain.schemas import ActionStatus, PendingAction

logger = logging.getLogger(__name__)


class ActionStore:
    """Pending action queue backed by Redis with in-memory fallback."""

    def __init__(self, working: WorkingMemory) -> None:
        self._working = working
        self._local: dict[str, PendingAction] = {}

    def _key(self, action_id: str) -> str:
        return f"action:{action_id}"

    async def save(self, action: PendingAction) -> PendingAction:
        payload = action.model_dump(mode="json")
        await self._working.set("actions", self._key(action.id), payload, ttl_seconds=3600)
        self._local[action.id] = action
        return action

    async def get(self, action_id: str) -> PendingAction | None:
        if action_id in self._local:
            return self._local[action_id]
        raw = await self._working.get("actions", self._key(action_id))
        if not raw:
            return None
        action = PendingAction(**raw)
        self._local[action_id] = action
        return action

    async def update(self, action: PendingAction) -> PendingAction:
        return await self.save(action)

    async def list_pending(self) -> list[PendingAction]:
        return [a for a in self._local.values() if a.status == ActionStatus.PENDING]


class IoTControlPlane:
    """Simulated or MQTT-backed BACnet/MQTT control plane."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._history: list[dict[str, Any]] = []
        self._mqtt = None
        if settings.mqtt_enabled:
            try:
                from second_brain.ingestion.mqtt.bridge import MqttCommandPublisher

                self._mqtt = MqttCommandPublisher(settings)
            except Exception as exc:  # noqa: BLE001
                logger.warning("MQTT control publisher not available: %s", exc)

    def execute(self, action: PendingAction) -> tuple[bool, str]:
        proposed = action.proposed
        if self.settings.iot_dry_run:
            msg = (
                f"[DRY-RUN] {proposed.command} device={proposed.device_id} "
                f"value={proposed.value} zone={proposed.zone_id}"
            )
            self._history.append({"dry_run": True, "action_id": action.id, "command": proposed.command})
            return True, msg

        if self._mqtt:
            ok = self._mqtt.publish_command(
                proposed.device_id, proposed.command, proposed.value, proposed.zone_id
            )
            if ok:
                msg = (
                    f"[MQTT] Published {proposed.command} to {proposed.device_id} "
                    f"value={proposed.value}"
                )
                self._history.append({"mqtt": True, "action_id": action.id})
                return True, msg

        msg = (
            f"[EXECUTED] {proposed.command} applied to {proposed.device_id} "
            f"value={proposed.value}"
        )
        self._history.append({"dry_run": False, "action_id": action.id, "command": proposed.command})
        return True, msg

    def close(self) -> None:
        if self._mqtt:
            self._mqtt.close()

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)
