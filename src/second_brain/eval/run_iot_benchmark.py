"""Evaluate IoT anomaly → action policy correctness."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from second_brain.config import get_settings
from second_brain.schemas import IoTTelemetryEvent
from second_brain.services.container import ServiceContainer

logger = logging.getLogger(__name__)


async def run_iot_benchmark(dataset_path: Path | None = None) -> dict:
    dataset_path = dataset_path or Path("eval/benchmarks/iot_actions.json")
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))

    settings = get_settings()
    container = ServiceContainer(settings)
    await container.startup()

    results = []
    for case in cases:
        for value in case["warmup_values"]:
            await container.process_iot(
                IoTTelemetryEvent(
                    device_id=case["device_id"],
                    zone_id=case["zone_id"],
                    metric=case["metric"],
                    value=float(value),
                )
            )

        outcome = await container.process_iot(
            IoTTelemetryEvent(
                device_id=case["device_id"],
                zone_id=case["zone_id"],
                metric=case["metric"],
                value=float(case["anomaly_value"]),
            )
        )

        action = outcome.get("action", {})
        proposed = action.get("proposed", {})
        command_ok = proposed.get("command") == case["expected_command"]
        policy_ok = case["expected_policy_pass"] == (
            action.get("status") in {"pending", "executed"}
        )
        if case.get("force_value") is not None:
            proposed_value = proposed.get("value")
            value_ok = proposed_value is not None and proposed_value <= settings.iot_comfort_max_c
        else:
            value_ok = settings.iot_comfort_min_c <= proposed.get("value", 0) <= settings.iot_comfort_max_c

        passed = command_ok and policy_ok and value_ok and outcome.get("anomaly_detected")
        results.append(
            {
                "case_id": case["id"],
                "passed": passed,
                "command_ok": command_ok,
                "policy_ok": policy_ok,
                "value_ok": value_ok,
                "anomaly_detected": outcome.get("anomaly_detected"),
                "action_status": action.get("status"),
            }
        )
        logger.info("IoT case %s passed=%s", case["id"], passed)

    await container.shutdown()
    passed_n = sum(1 for r in results if r["passed"])
    return {
        "count": len(results),
        "passed": passed_n,
        "action_correctness": round(passed_n / max(1, len(results)), 4),
        "results": results,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(asyncio.run(run_iot_benchmark()), indent=2))


if __name__ == "__main__":
    main()
