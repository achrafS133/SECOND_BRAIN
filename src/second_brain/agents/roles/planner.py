from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from second_brain.config import Settings


def build_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key or "not-set",
        base_url=settings.openai_base_url,
        temperature=0.2,
    )


def heuristic_answer(query: str, context_text: str) -> tuple[str, list[str]]:
    """Fallback planner when LLM is not configured."""
    plan = [
        "Load tiered memory context",
        "Scan retrieved evidence for relevant facts",
        "Synthesize answer grounded in evidence",
    ]
    evidence_snippet = ""
    if "Evidence:" in context_text:
        evidence_snippet = context_text.split("Evidence:", maxsplit=1)[1][:800].strip()
    if evidence_snippet:
        answer = (
            f"Based on retrieved memory for '{query}':\n\n{evidence_snippet}\n\n"
            "(Configure OPENAI_API_KEY for full multi-agent reasoning.)"
        )
    else:
        answer = (
            f"I processed your query '{query}' but no long-term evidence was found yet. "
            "Ingest documents via POST /ingest/document, then retry."
        )
    return answer, plan
