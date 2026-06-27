"""Eval metrics.

Two axes, deliberately kept distinct:

- ``score_routing`` (deterministic): did the agent's control flow do the right
  thing — call the tools it should have, and only those? No LLM, no cost.
- ``judge_quality`` (LLM-as-judge): is the answer actually *good* — correct,
  complete, and respectful of the assistant's opening-only scope?

Grounding/faithfulness is intentionally not here yet (deferred); the rubric is
scoped to answer quality so it stays a clean, separate axis from grounding.

The judge is reference-assisted: it sees the gold answer as a guide but is told
to reward correct answers that differ in wording. Self-preference bias note: the
judge model should ideally differ from the agent model; ``run_eval`` is the
composition root that picks the concrete judge and injects it here.
"""

from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from tests.eval.dataset import EvalRecord

# --- Routing accuracy (deterministic) ---------------------------------------


@dataclass
class RoutingResult:
    expected: list[str]
    actual: list[str]
    passed: bool


def score_routing(expected_tools: list[str], actual_tools: list[str]) -> RoutingResult:
    """Exact set match between expected and actually-called model tools.

    Set (not list) comparison: order and duplicate calls don't matter, only
    *which* tools fired. An empty expected set means the agent should answer
    without calling any tool.
    """
    passed = set(expected_tools) == set(actual_tools)
    return RoutingResult(expected=expected_tools, actual=actual_tools, passed=passed)


# --- Response quality (LLM-as-judge) ----------------------------------------

# The concrete judge model is chosen in ``run_eval`` and passed into
# ``judge_quality``; this module stays model-agnostic. Bias note: the judge
# should ideally differ from the agent under test to limit self-preference.


class QualityScore(BaseModel):
    """Rubric scores on a 1-5 scale, with a short justification."""

    correctness: int = Field(ge=1, le=5, description="Factual/chess accuracy")
    completeness: int = Field(ge=1, le=5, description="Covers what the question asks")
    scope_adherence: int = Field(
        ge=1,
        le=5,
        description="Stays within opening theory; refuses when out of scope",
    )
    reasoning: str = Field(description="One or two sentences justifying the scores")

    @property
    def overall(self) -> float:
        return (self.correctness + self.completeness + self.scope_adherence) / 3


_JUDGE_PROMPT = """You are grading a chess-opening assistant's answer.

The assistant is restricted to opening theory (roughly the first 6 moves). For \
positions that are too deep or otherwise out of scope, the correct behaviour is \
to decline rather than guess.

Score the candidate answer on three axes, each 1 (poor) to 5 (excellent):
- correctness: is the chess content accurate?
- completeness: does it actually answer what was asked?
- scope_adherence: does it stay within opening theory, and decline when the \
position is out of scope?

Use the reference answer as a guide to what a good response looks like, but \
reward correct answers that are phrased differently. This position is marked \
{scope_note}.

Question:
{question}

Position (PGN): {pgn}

Reference answer (guide, not the only acceptable answer):
{reference_answer}

Candidate answer to grade:
{candidate_answer}
"""


async def judge_quality(
    judge: BaseChatModel, record: EvalRecord, candidate_answer: str
) -> QualityScore:
    structured = judge.with_structured_output(QualityScore)
    prompt = _JUDGE_PROMPT.format(
        scope_note="IN SCOPE" if record.in_scope else "OUT OF SCOPE",
        question=record.question,
        pgn=record.pgn or "(none)",
        reference_answer=record.reference_answer,
        candidate_answer=candidate_answer,
    )
    return await structured.ainvoke(prompt)  # type: ignore[return-value]
