from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class CogOSState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    query: str
    task_type: str
    context_text: str
    plan: list[str]
    draft_answer: str
    tool_results: list[dict]
    critic_verdict: str
    critic_feedback: str
    audit_trail: list[dict]
    iteration: int
