import pytest

from second_brain.agents.roles.critic import evaluate_answer
from second_brain.memory.tiers.short_term import ShortTermMemory
from second_brain.schemas import EvidencePackage, GraphNode


def test_short_term_assemble_respects_budget():
    stm = ShortTermMemory(token_budget=200)
    stm.append_turn("user", "hello world " * 50)
    bundle = stm.assemble()
    assert bundle.estimated_tokens <= 200


def test_critic_accepts_honest_uncertainty():
    verdict, _ = evaluate_answer("No long-term evidence was found yet.", None)
    assert verdict.value == "accept"


def test_critic_revises_without_evidence():
    verdict, feedback = evaluate_answer(
        "The checkout service failed because of database corruption.",
        EvidencePackage(),
    )
    assert verdict.value == "revise"
    assert feedback
