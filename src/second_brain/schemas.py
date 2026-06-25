from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ObservationKind(StrEnum):
    OBSERVATION = "observation"
    REFLECTION = "reflection"
    PLAN = "plan"


class TaskType(StrEnum):
    QA = "qa"
    ACTION = "action"
    ANOMALY = "anomaly"


class CriticVerdict(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class MemoryObservation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    kind: ObservationKind = ObservationKind.OBSERVATION
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source_uri: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class EvidencePackage(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    community_summary: str | None = None
    provenance: list[str] = Field(default_factory=list)
    retrieval_score: float = 0.0


class ContextBundle(BaseModel):
    core_blocks: list[str] = Field(default_factory=list)
    dialogue_turns: list[str] = Field(default_factory=list)
    pinned_working_state: dict[str, Any] = Field(default_factory=dict)
    retrieved_evidence: EvidencePackage | None = None
    estimated_tokens: int = 0


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    trace_id: str
    agent: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProposedAction(BaseModel):
    device_id: str
    zone_id: str
    command: str
    value: float
    rationale: str
    metric: str | None = None


class PendingAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: ActionStatus = ActionStatus.PENDING
    proposed: ProposedAction
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    policy_checks: list[str] = Field(default_factory=list)
    execution_result: str | None = None


class ActionDecision(BaseModel):
    approved: bool
    reviewer: str = "operator"
    note: str = ""


class QueryRequest(BaseModel):
    query: str
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: TaskType = TaskType.QA
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    session_id: str
    evidence: EvidencePackage | None = None
    critic_verdict: CriticVerdict
    plan: list[str] = Field(default_factory=list)
    audit_trail: list[AuditEvent] = Field(default_factory=list)
    pending_action_id: str | None = None


class IngestDocumentRequest(BaseModel):
    uri: str
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IoTTelemetryEvent(BaseModel):
    device_id: str
    zone_id: str
    metric: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BenchmarkCase(BaseModel):
    id: str
    query: str
    expected_keywords: list[str] = Field(default_factory=list)
    expected_entities: list[str] = Field(default_factory=list)


class BenchmarkResult(BaseModel):
    case_id: str
    query: str
    answer: str
    faithfulness: float
    answer_relevance: float
    graph_grounding: float
    latency_ms: float
