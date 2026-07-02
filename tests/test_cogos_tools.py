import pytest
from langchain_core.messages import AIMessage

from second_brain.agents.graph.cogos import CogOSGraph
from second_brain.config import Settings
from second_brain.memory.manager import MemoryManager
from second_brain.memory.retrieval.embeddings import EmbeddingService
from second_brain.memory.tiers.long_term import LongTermMemory
from second_brain.memory.tiers.short_term import ShortTermMemory
from second_brain.memory.tiers.working import WorkingMemory


@pytest.fixture
def cogos_graph():
    settings = Settings()
    working = WorkingMemory(settings)
    short_term = ShortTermMemory(token_budget=settings.context_token_budget)
    long_term = LongTermMemory(settings)
    memory = MemoryManager(working, short_term, long_term)
    embeddings = EmbeddingService(settings)
    return CogOSGraph(settings, memory, embeddings)


async def test_tool_executor_runs_search_and_iot_tools(cogos_graph):
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge_base_tool",
                        "args": {"query": "memory tiers"},
                        "id": "call-1",
                    },
                    {
                        "name": "simulate_iot_action_tool",
                        "args": {
                            "device_id": "hvac-1",
                            "command": "set_setpoint",
                            "value": 22.0,
                        },
                        "id": "call-2",
                    },
                ],
            )
        ],
        "query": "memory tiers",
        "tool_results": [{"evidence_nodes": []}],
        "audit_trail": [],
        "session_id": "test-session",
    }

    result = await cogos_graph.tool_executor(state)

    assert len(result["messages"]) == 3
    assert len(result["tool_results"]) == 3
    assert len(result["audit_trail"]) == 2
    assert "call_search_knowledge_base_tool" in result["audit_trail"][0]["action"]
    assert "hvac-1" in result["messages"][-1].content


def test_route_after_planner_with_tool_calls(cogos_graph):
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "search_knowledge_base_tool", "args": {}, "id": "1"}],
            )
        ]
    }
    assert cogos_graph._route_after_planner(state) == "tool_executor"


def test_route_after_planner_without_tools_goes_to_critic(cogos_graph):
    state = {"messages": [], "draft_answer": "done"}
    assert cogos_graph._route_after_planner(state) == "critic"
