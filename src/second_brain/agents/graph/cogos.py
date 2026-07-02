from __future__ import annotations

import logging
from typing import Literal
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph

from second_brain.agents.graph.state import CogOSState
from second_brain.agents.roles.critic import evaluate_answer
from second_brain.agents.roles.planner import build_llm, heuristic_answer
from second_brain.agents.tools.registry import emit_audit_event, search_knowledge_base, simulate_iot_action
from second_brain.config import Settings
from second_brain.eval.ablation.config import FULL_COGOS, AblationProfile
from second_brain.memory.manager import MemoryManager
from second_brain.memory.retrieval.embeddings import EmbeddingService
from second_brain.schemas import CriticVerdict, QueryResponse, TaskType

logger = logging.getLogger(__name__)
MAX_ITERATIONS = 2


@tool
def search_knowledge_base_tool(query: str) -> str:
    """Search the retrieved long-term memory chunks/knowledge hits for facts matching the query."""
    return ""


@tool
def simulate_iot_action_tool(device_id: str, command: str, value: float) -> str:
    """Simulate applying an IoT actuation command and value to a device."""
    return ""


class CogOSGraph:
    def __init__(
        self,
        settings: Settings,
        memory_manager: MemoryManager,
        embedding_service: EmbeddingService,
        ablation: AblationProfile | None = None,
    ) -> None:
        self.settings = settings
        self.memory = memory_manager
        self.embeddings = embedding_service
        self.ablation = ablation or FULL_COGOS
        self.tools = [search_knowledge_base_tool, simulate_iot_action_tool]
        self.graph = self._build()

    def _build(self):
        workflow = StateGraph(CogOSState)
        workflow.add_node("orchestrator", self.orchestrator)
        workflow.add_node("memory_load", self.memory_load)
        workflow.add_node("planner", self.planner)
        workflow.add_node("tool_executor", self.tool_executor)
        workflow.set_entry_point("orchestrator")
        workflow.add_edge("orchestrator", "memory_load")
        workflow.add_edge("memory_load", "planner")

        planner_routes = {
            "tool_executor": "tool_executor",
        }
        if self.ablation.use_critic:
            planner_routes["critic"] = "critic"
        else:
            planner_routes["finish"] = END

        workflow.add_conditional_edges(
            "planner",
            self._route_after_planner,
            planner_routes,
        )
        workflow.add_edge("tool_executor", "planner")

        if self.ablation.use_critic:
            workflow.add_node("critic", self.critic)
            workflow.add_conditional_edges(
                "critic",
                self._route_after_critic,
                {"revise": "planner", "finish": END},
            )

        return workflow.compile()

    async def orchestrator(self, state: CogOSState) -> dict:
        trace_id = str(uuid4())
        audit = emit_audit_event(trace_id, "orchestrator", "route_task", {"query": state["query"]})
        return {
            "audit_trail": state.get("audit_trail", []) + [audit.metadata],
            "iteration": state.get("iteration", 0),
        }

    async def memory_load(self, state: CogOSState) -> dict:
        embedding = self.embeddings.embed_query(state["query"])
        bundle = await self.memory.assemble_context(
            session_id=state["session_id"],
            query=state["query"],
            query_embedding=embedding,
            top_k=self.settings.retrieval_top_k,
        )
        context_text = self.memory.format_context_for_llm(bundle)
        await self.memory.record_turn("user", state["query"])
        evidence_nodes = []
        if bundle.retrieved_evidence:
            evidence_nodes = [n.model_dump() for n in bundle.retrieved_evidence.nodes]
        return {
            "context_text": context_text,
            "tool_results": [{"evidence_nodes": evidence_nodes}],
        }

    async def planner(self, state: CogOSState) -> dict:
        iteration = state.get("iteration", 0) + 1
        messages = list(state.get("messages", []))

        if not messages:
            system = SystemMessage(
                content=(
                    "You are the Planner agent in The Second Brain CogOS. "
                    "Use ONLY the provided context and tools. Return a concise, grounded answer."
                )
            )
            human = HumanMessage(
                content=f"Context:\n{state['context_text']}\n\nQuery: {state['query']}"
            )
            messages = [system, human]

        if state.get("critic_feedback"):
            messages.append(HumanMessage(content=f"Critic feedback: {state['critic_feedback']}"))

        if self.settings.llm_configured:
            try:
                llm = build_llm(self.settings)
                llm_with_tools = llm.bind_tools(self.tools)
                response = await llm_with_tools.ainvoke(messages)

                if hasattr(response, "tool_calls") and response.tool_calls:
                    return {
                        "messages": messages + [response],
                        "iteration": iteration,
                    }
                else:
                    return {
                        "messages": messages + [response],
                        "draft_answer": str(response.content),
                        "plan": ["LLM synthesis with retrieved context"],
                        "iteration": iteration,
                    }
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM planner failed, using heuristic: %s", exc)
                answer, plan = heuristic_answer(state["query"], state["context_text"])
                return {
                    "draft_answer": answer,
                    "plan": plan,
                    "iteration": iteration,
                }
        else:
            answer, plan = heuristic_answer(state["query"], state["context_text"])
            return {
                "draft_answer": answer,
                "plan": plan,
                "iteration": iteration,
            }

    async def tool_executor(self, state: CogOSState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return {}

        last_message = messages[-1]
        if not (hasattr(last_message, "tool_calls") and last_message.tool_calls):
            return {}

        evidence_nodes = []
        if state.get("tool_results"):
            evidence_nodes = state["tool_results"][0].get("evidence_nodes", [])

        new_messages = []
        tool_results = list(state.get("tool_results", []))
        audit_trail = list(state.get("audit_trail", []))

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]

            output = ""
            if tool_name == "search_knowledge_base_tool":
                q = args.get("query", state["query"])
                res = search_knowledge_base(q, evidence_nodes)
                output = res.output
                tool_results.append(res.model_dump())
            elif tool_name == "simulate_iot_action_tool":
                device_id = args.get("device_id")
                command = args.get("command")
                value = args.get("value", 0.0)
                res = simulate_iot_action(device_id, command, value)
                output = res.output
                tool_results.append(res.model_dump())
            else:
                output = f"Unknown tool: {tool_name}"

            trace_id = state.get("session_id", "local-session")
            audit = emit_audit_event(
                trace_id=trace_id,
                agent="planner",
                action=f"call_{tool_name}",
                payload={"args": args, "output": output},
            )
            audit_trail.append(audit.metadata)

            new_messages.append(
                ToolMessage(
                    content=output,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

        return {
            "messages": messages + new_messages,
            "tool_results": tool_results,
            "audit_trail": audit_trail,
        }

    async def critic(self, state: CogOSState) -> dict:
        evidence = None
        if state.get("tool_results"):
            from second_brain.schemas import EvidencePackage, GraphNode

            # The first entry in tool_results contains evidence nodes from memory_load
            nodes_raw = state["tool_results"][0].get("evidence_nodes", [])
            evidence = EvidencePackage(
                nodes=[GraphNode(**n) for n in nodes_raw if isinstance(n, dict)]
            )
        verdict, feedback = evaluate_answer(
            state.get("draft_answer", ""),
            evidence,
            task_type=state.get("task_type", "qa"),
        )
        return {"critic_verdict": verdict.value, "critic_feedback": feedback}

    def _route_after_planner(self, state: CogOSState) -> Literal["tool_executor", "critic", "finish"]:
        messages = state.get("messages", [])
        if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
            return "tool_executor"
        if self.ablation.use_critic:
            return "critic"
        return "finish"

    def _route_after_critic(self, state: CogOSState) -> Literal["revise", "finish"]:
        if state.get("critic_verdict") == CriticVerdict.REVISE.value and state.get(
            "iteration", 0
        ) < MAX_ITERATIONS:
            return "revise"
        return "finish"

    async def run(
        self,
        query: str,
        session_id: str,
        task_type: TaskType = TaskType.QA,
    ) -> QueryResponse:
        initial: CogOSState = {
            "messages": [],
            "session_id": session_id,
            "query": query,
            "task_type": task_type.value,
            "context_text": "",
            "plan": [],
            "draft_answer": "",
            "tool_results": [],
            "critic_verdict": "",
            "critic_feedback": "",
            "audit_trail": [],
            "iteration": 0,
        }
        final = await self.graph.ainvoke(initial)
        await self.memory.record_turn("assistant", final.get("draft_answer", ""))

        from second_brain.schemas import AuditEvent, EvidencePackage, GraphNode

        evidence = None
        if final.get("tool_results"):
            nodes_raw = final["tool_results"][0].get("evidence_nodes", [])
            if nodes_raw:
                evidence = EvidencePackage(nodes=[GraphNode(**n) for n in nodes_raw])

        audit = [
            AuditEvent(
                trace_id=e.get("trace_id", "local"),
                agent=e.get("agent", "unknown"),
                action=e.get("action", "event"),
                payload=e.get("payload", {}),
            )
            for e in final.get("audit_trail", [])
            if isinstance(e, dict)
        ]

        return QueryResponse(
            answer=final.get("draft_answer", ""),
            session_id=session_id,
            evidence=evidence,
            critic_verdict=CriticVerdict(
                final.get("critic_verdict") or CriticVerdict.ACCEPT.value
            ),
            plan=final.get("plan", []),
            audit_trail=audit,
        )
