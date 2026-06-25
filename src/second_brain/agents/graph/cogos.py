from __future__ import annotations

import logging
from typing import Literal
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from second_brain.agents.graph.state import CogOSState
from second_brain.agents.roles.critic import evaluate_answer
from second_brain.agents.roles.planner import build_llm, heuristic_answer
from second_brain.agents.tools.registry import emit_audit_event, search_knowledge_base
from second_brain.config import Settings
from second_brain.eval.ablation.config import FULL_COGOS, AblationProfile
from second_brain.memory.manager import MemoryManager
from second_brain.memory.retrieval.embeddings import EmbeddingService
from second_brain.schemas import CriticVerdict, QueryResponse, TaskType

logger = logging.getLogger(__name__)
MAX_ITERATIONS = 2


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
        workflow.add_edge("planner", "tool_executor")

        if self.ablation.use_critic:
            workflow.add_node("critic", self.critic)
            workflow.add_edge("tool_executor", "critic")
            workflow.add_conditional_edges(
                "critic",
                self._route_after_critic,
                {"revise": "planner", "finish": END},
            )
        else:
            workflow.add_edge("tool_executor", END)

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
        if self.settings.llm_configured:
            try:
                llm = build_llm(self.settings)
                system = SystemMessage(
                    content=(
                        "You are the Planner agent in The Second Brain CogOS. "
                        "Use ONLY the provided context. Return a concise, grounded answer."
                    )
                )
                human = HumanMessage(
                    content=f"Context:\n{state['context_text']}\n\nQuery: {state['query']}"
                )
                if state.get("critic_feedback"):
                    human = HumanMessage(
                        content=(
                            f"{human.content}\n\nCritic feedback: {state['critic_feedback']}"
                        )
                    )
                response = await llm.ainvoke([system, human])
                answer = str(response.content)
                plan = ["LLM synthesis with retrieved context"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM planner failed, using heuristic: %s", exc)
                answer, plan = heuristic_answer(state["query"], state["context_text"])
        else:
            answer, plan = heuristic_answer(state["query"], state["context_text"])

        return {"draft_answer": answer, "plan": plan, "iteration": iteration}

    async def tool_executor(self, state: CogOSState) -> dict:
        evidence_nodes = []
        if state.get("tool_results"):
            evidence_nodes = state["tool_results"][0].get("evidence_nodes", [])
        result = search_knowledge_base(state["query"], evidence_nodes)
        return {"tool_results": state.get("tool_results", []) + [result.model_dump()]}

    async def critic(self, state: CogOSState) -> dict:
        evidence = None
        if state.get("tool_results"):
            from second_brain.schemas import EvidencePackage, GraphNode

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
