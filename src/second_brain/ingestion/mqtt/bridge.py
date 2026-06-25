from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING

from second_brain.config import Settings

if TYPE_CHECKING:
    from second_brain.services.container import ServiceContainer

logger = logging.getLogger(__name__)


class MqttCommandPublisher:
    """Publish IoT control commands to MQTT (when dry-run is disabled)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None
        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"second-brain-control-{uuid.uuid4().hex[:8]}",
            )
            self._client.connect(settings.mqtt_broker, settings.mqtt_port, keepalive=60)
            self._client.loop_start()
            logger.info("MQTT command publisher connected to %s", settings.mqtt_broker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MQTT publisher unavailable: %s", exc)
            self._client = None

    def publish_command(
        self, device_id: str, command: str, value: float, zone_id: str
    ) -> bool:
        if not self._client:
            return False
        topic = self.settings.mqtt_command_topic_template.format(device_id=device_id)
        payload = json.dumps(
            {"command": command, "value": value, "zone_id": zone_id, "source": "second-brain"}
        )
        result = self._client.publish(topic, payload, qos=1)
        return result.rc == 0

    def close(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()


class MqttTelemetryBridge:
    """Subscribe to telemetry topics and forward events into CogOS."""

    def __init__(self, settings: Settings, container: ServiceContainer) -> None:
        self.settings = settings
        self.container = container
        self._client = None

    async def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError("Install mqtt extras: pip install 'second-brain[mqtt]'") from exc

        bridge = self
        loop = asyncio.get_running_loop()

        def on_message(client, userdata, msg):  # noqa: ARG001
            try:
                payload = json.loads(msg.payload.decode())
                from second_brain.schemas import IoTTelemetryEvent

                event = IoTTelemetryEvent(
                    device_id=payload.get("device_id", "unknown"),
                    zone_id=payload.get("zone_id", "default"),
                    metric=payload.get("metric", "value"),
                    value=float(payload["value"]),
                )
                future = asyncio.run_coroutine_threadsafe(
                    bridge.container.process_iot(event), loop
                )

                def _log_future_result(done):  # noqa: ANN001
                    try:
                        done.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("MQTT IoT processing failed: %s", exc)

                future.add_done_callback(_log_future_result)
                logger.info(
                    "MQTT telemetry received device=%s metric=%s value=%s",
                    event.device_id,
                    event.metric,
                    event.value,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Invalid MQTT telemetry payload: %s", exc)

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"second-brain-telemetry-{uuid.uuid4().hex[:8]}",
        )
        self._client.on_message = on_message
        self._client.connect(self.settings.mqtt_broker, self.settings.mqtt_port, keepalive=60)
        self._client.subscribe(self.settings.mqtt_telemetry_topic)
        self._client.loop_start()
        logger.info(
            "MQTT telemetry bridge subscribed to %s",
            self.settings.mqtt_telemetry_topic,
        )

    async def stop(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
