from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from second_brain.config import Settings


def build_llm(settings: Settings) -> ChatOpenAI:
    provider = settings.llm_provider.lower()
    temperature = settings.llm_temperature

    if provider == "nvidia":
        extra_body = None
        if settings.llm_enable_thinking:
            extra_body = {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": settings.llm_reasoning_budget,
            }
        return ChatOpenAI(
            model=settings.active_llm_model,
            api_key=settings.nvidia_api_key or "not-set",
            base_url=settings.nvidia_base_url,
            temperature=temperature,
            extra_body=extra_body,
        )

    if provider == "ollama":
        return ChatOpenAI(
            model=settings.active_llm_model,
            api_key=settings.ollama_api_key or "ollama",
            base_url=settings.ollama_base_url,
            temperature=temperature,
        )

    return ChatOpenAI(
        model=settings.active_llm_model,
        api_key=settings.openai_api_key or "not-set",
        base_url=settings.openai_base_url,
        temperature=temperature,
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
            "(Configure LLM_PROVIDER and API keys in .env for full multi-agent reasoning.)"
        )
    else:
        answer = (
            f"I processed your query '{query}' but no long-term evidence was found yet. "
            "Ingest documents via POST /ingest/document, then retry."
        )
    return answer, plan
