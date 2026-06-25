from __future__ import annotations

import logging
from uuid import uuid4

from second_brain.agents.roles.action_policy import (
    ActionPolicyEngine,
    propose_action_from_anomaly,
)
from second_brain.config import Settings
from second_brain.schemas import (
    ActionDecision,
    ActionStatus,
    AuditEvent,
    PendingAction,
    ProposedAction,
)
from second_brain.services.action_service import ActionStore, IoTControlPlane

logger = logging.getLogger(__name__)


class ActionOrchestrator:
    """Phase 4 — propose, approve, and execute IoT actions with policy gates."""

    def __init__(
        self,
        settings: Settings,
        action_store: ActionStore,
        control_plane: IoTControlPlane,
    ) -> None:
        self.settings = settings
        self.store = action_store
        self.control = control_plane
        self.policy = ActionPolicyEngine(settings)

    async def propose(self, proposed: ProposedAction, session_id: str) -> PendingAction:
        ok, checks = self.policy.validate(proposed)
        action = PendingAction(
            proposed=proposed,
            session_id=session_id,
            policy_checks=checks,
            status=ActionStatus.REJECTED if not ok else ActionStatus.PENDING,
        )

        if not ok:
            action.execution_result = "Rejected by policy engine"
            return await self.store.save(action)

        if not self.policy.requires_human_approval(proposed):
            return await self._execute(action)

        return await self.store.save(action)

    async def propose_from_anomaly(
        self, device_id: str, zone_id: str, metric: str, stats: dict, session_id: str
    ) -> PendingAction:
        proposed = propose_action_from_anomaly(device_id, zone_id, metric, stats)
        return await self.propose(proposed, session_id=session_id)

    async def approve(self, action_id: str, decision: ActionDecision) -> PendingAction:
        action = await self.store.get(action_id)
        if not action:
            raise KeyError(f"Action {action_id} not found")
        if action.status != ActionStatus.PENDING:
            return action

        if decision.approved:
            action.status = ActionStatus.APPROVED
            await self.store.update(action)
            return await self._execute(action)

        action.status = ActionStatus.REJECTED
        action.execution_result = f"Rejected by {decision.reviewer}: {decision.note}"
        return await self.store.update(action)

    async def list_pending(self) -> list[PendingAction]:
        return await self.store.list_pending()

    async def _execute(self, action: PendingAction) -> PendingAction:
        success, message = self.control.execute(action)
        action.status = ActionStatus.EXECUTED if success else ActionStatus.FAILED
        action.execution_result = message
        logger.info("Action %s -> %s", action.id, action.status.value)
        return await self.store.update(action)

    def audit_event(self, action: PendingAction) -> AuditEvent:
        return AuditEvent(
            trace_id=str(uuid4()),
            agent="action_orchestrator",
            action=f"action_{action.status.value}",
            payload={
                "action_id": action.id,
                "command": action.proposed.command,
                "device_id": action.proposed.device_id,
                "result": action.execution_result,
            },
        )
