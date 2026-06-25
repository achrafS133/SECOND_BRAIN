from __future__ import annotations

from second_brain.config import Settings
from second_brain.schemas import ActionStatus, PendingAction, ProposedAction


class ActionPolicyEngine:
    """Validates IoT actuation against comfort and safety bounds."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self, action: ProposedAction) -> tuple[bool, list[str]]:
        checks: list[str] = []
        ok = True

        if action.command not in {"set_setpoint", "reduce_load", "notify_operator"}:
            ok = False
            checks.append(f"Unsupported command: {action.command}")

        if action.command == "set_setpoint":
            if not (self.settings.iot_comfort_min_c <= action.value <= self.settings.iot_comfort_max_c):
                ok = False
                checks.append(
                    f"Setpoint {action.value} outside comfort band "
                    f"[{self.settings.iot_comfort_min_c}, {self.settings.iot_comfort_max_c}]"
                )

        if "override safety" in action.rationale.lower():
            ok = False
            checks.append("Policy violation: unsafe rationale")

        if ok:
            checks.append("Policy checks passed")
        return ok, checks

    def requires_human_approval(self, action: ProposedAction) -> bool:
        if not self.settings.require_human_approval:
            return False
        return action.command in {"set_setpoint", "reduce_load"}


def propose_action_from_anomaly(
    device_id: str,
    zone_id: str,
    metric: str,
    stats: dict,
) -> ProposedAction:
    mean = float(stats.get("mean", 0))
    last = float(stats.get("last_value", mean))

    if metric == "temperature" and last > mean:
        target = max(18.0, min(26.0, mean))
        return ProposedAction(
            device_id=device_id,
            zone_id=zone_id,
            command="set_setpoint",
            value=round(target, 2),
            rationale=f"Temperature anomaly detected ({last} vs mean {mean}); restore nominal setpoint.",
            metric=metric,
        )

    return ProposedAction(
        device_id=device_id,
        zone_id=zone_id,
        command="notify_operator",
        value=0.0,
        rationale=f"Anomaly on {metric}; escalate to operator.",
        metric=metric,
    )
