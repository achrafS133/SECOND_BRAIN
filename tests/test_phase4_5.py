from second_brain.agents.roles.action_policy import ActionPolicyEngine, propose_action_from_anomaly
from second_brain.config import Settings
from second_brain.schemas import ActionDecision, ProposedAction
from second_brain.services.action_service import ActionStore, IoTControlPlane
from second_brain.services.action_orchestrator import ActionOrchestrator
from second_brain.memory.tiers.working import WorkingMemory


def test_policy_rejects_unsafe_rationale():
    settings = Settings(require_human_approval=True)
    engine = ActionPolicyEngine(settings)
    action = ProposedAction(
        device_id="d1",
        zone_id="z1",
        command="set_setpoint",
        value=22.0,
        rationale="override safety limits immediately",
    )
    ok, checks = engine.validate(action)
    assert ok is False
    assert any("unsafe" in c.lower() for c in checks)


def test_policy_accepts_valid_setpoint():
    settings = Settings(require_human_approval=True)
    engine = ActionPolicyEngine(settings)
    action = ProposedAction(
        device_id="d1",
        zone_id="z1",
        command="set_setpoint",
        value=22.0,
        rationale="Restore comfort after anomaly",
    )
    ok, _ = engine.validate(action)
    assert ok is True


def test_propose_from_anomaly_temperature():
    action = propose_action_from_anomaly(
        "dev-1", "zone-a", "temperature", {"mean": 22.0, "last_value": 45.0}
    )
    assert action.command == "set_setpoint"
    assert 18.0 <= action.value <= 26.0


async def test_action_orchestrator_pending_then_execute():
    settings = Settings(require_human_approval=True, iot_dry_run=True)
    working = WorkingMemory(settings)
    await working.connect()
    store = ActionStore(working)
    control = IoTControlPlane(settings)
    orchestrator = ActionOrchestrator(settings, store, control)

    proposed = ProposedAction(
        device_id="d1",
        zone_id="z1",
        command="set_setpoint",
        value=21.0,
        rationale="Test action",
    )
    pending = await orchestrator.propose(proposed, session_id="sess-1")
    assert pending.status.value == "pending"

    executed = await orchestrator.approve(
        pending.id,
        ActionDecision(approved=True, reviewer="test"),
    )
    assert executed.status.value == "executed"
    assert "[DRY-RUN]" in (executed.execution_result or "")
    await working.close()


def test_benchmark_scorers():
    from second_brain.eval.metrics.scorers import answer_relevance, keyword_faithfulness
    from second_brain.schemas import EvidencePackage, GraphNode

    evidence = EvidencePackage(
        nodes=[GraphNode(id="1", label="Chunk", properties={"text": "PaymentGateway latency"})]
    )
    score = keyword_faithfulness(
        "Check PaymentGateway for latency issues",
        evidence,
        ["PaymentGateway", "latency"],
    )
    assert score >= 0.5
    rel = answer_relevance(
        "checkout latency spike",
        "Inspect PaymentGateway upstream dependencies",
        ["PaymentGateway"],
    )
    assert rel > 0
