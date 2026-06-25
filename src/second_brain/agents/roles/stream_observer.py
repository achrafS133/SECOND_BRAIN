from __future__ import annotations

from second_brain.ingestion.stream.window import WindowStats
from second_brain.schemas import IoTTelemetryEvent, TaskType


class StreamObserver:
    """Detects stream anomalies and produces agent-ready summaries."""

    def __init__(self, sigma: float = 3.0) -> None:
        self.sigma = sigma
        self._windows: dict[str, WindowStats] = {}

    def _key(self, event: IoTTelemetryEvent) -> str:
        return f"{event.device_id}:{event.metric}"

    def observe(self, event: IoTTelemetryEvent) -> dict:
        key = self._key(event)
        if key not in self._windows:
            self._windows[key] = WindowStats(
                device_id=event.device_id,
                zone_id=event.zone_id,
                metric=event.metric,
            )
        window = self._windows[key]
        window.update(event.value)
        stats = window.to_dict()
        anomaly = window.is_anomaly(self.sigma)

        summary = (
            f"Device {event.device_id} ({event.zone_id}) {event.metric}="
            f"{event.value} mean={stats['mean']} stdev={stats['stdev']}"
        )
        if anomaly:
            summary = f"ANOMALY: {summary} exceeds {self.sigma} sigma"

        return {
            "stats": stats,
            "anomaly_detected": anomaly,
            "summary": summary,
            "recommended_task": TaskType.ANOMALY if anomaly else TaskType.QA,
            "pin_payload": {
                "stream_summary": summary,
                "stats": stats,
                "anomaly": anomaly,
            },
        }
