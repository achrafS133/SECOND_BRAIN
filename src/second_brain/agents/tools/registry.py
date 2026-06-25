from __future__ import annotations

import json
from typing import Any

from second_brain.schemas import ToolResult


def search_knowledge_base(query: str, evidence_nodes: list[dict]) -> ToolResult:
    if not evidence_nodes:
        return ToolResult(
            tool_name="search_knowledge_base",
            success=True,
            output="No nodes in evidence bundle.",
        )
    lines = [f"- {n.get('properties', {}).get('text', n.get('id'))}" for n in evidence_nodes[:5]]
    return ToolResult(
        tool_name="search_knowledge_base",
        success=True,
        output="Knowledge hits:\n" + "\n".join(lines),
    )


def emit_audit_event(trace_id: str, agent: str, action: str, payload: dict[str, Any]) -> ToolResult:
    event = {"trace_id": trace_id, "agent": agent, "action": action, "payload": payload}
    return ToolResult(
        tool_name="emit_audit_event",
        success=True,
        output=json.dumps(event),
        metadata=event,
    )


def simulate_iot_action(device_id: str, command: str, value: float) -> ToolResult:
    return ToolResult(
        tool_name="simulate_iot_action",
        success=True,
        output=f"Applied {command}={value} to device {device_id} (simulated).",
        metadata={"device_id": device_id, "command": command, "value": value},
    )
