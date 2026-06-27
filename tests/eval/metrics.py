"""Eval metrics.

Two axes, deliberately kept distinct:

- ``score_routing`` (deterministic): did the agent's control flow do the right
  thing — call the tools it should have, and only those? No LLM, no cost.
- ``judge_quality`` (LLM-as-judge): is the answer actually *good* — correct,
  complete, and respectful of the assistant's opening-only scope?

The judge is reference-assisted: it sees the gold answer as a guide but is told
to reward correct answers that differ in wording. Self-preference bias note: the
judge model should ideally differ from the agent model; ``run_eval`` is the
composition root that picks the concrete judge model and passes it in.
"""

import hashlib
import json
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

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

The assistant operates under the instructions below (its system prompt). Judge \
scope_adherence against these actual rules rather than your own assumptions \
about what "in scope" means:

--- BEGIN ASSISTANT INSTRUCTIONS ---
{agent_system_prompt}
--- END ASSISTANT INSTRUCTIONS ---

The assistant also has access to these tools. An answer that reports their \
output — e.g. a concrete Stockfish engine evaluation, or master-game \
statistics — is using a real capability, so do NOT treat such results as \
hallucinated:

{available_tools}

Score the candidate answer on three axes, each 1 (poor) to 5 (excellent):
- correctness: is the chess content accurate? Judge this independently of the \
instructions above — following the instructions well does not make wrong chess \
right.
- completeness: does it actually answer what was asked?
- scope_adherence: does it follow the assistant instructions above — in \
particular staying within opening theory and declining when the position is \
out of scope?

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
    judge: BaseChatModel,
    *,
    question: str,
    pgn: str,
    in_scope: bool,
    reference_answer: str,
    candidate_answer: str,
    agent_system_prompt: str,
    available_tools: str,
) -> QualityScore:
    structured = judge.with_structured_output(QualityScore)
    prompt = _JUDGE_PROMPT.format(
        scope_note="IN SCOPE" if in_scope else "OUT OF SCOPE",
        question=question,
        pgn=pgn or "(none)",
        reference_answer=reference_answer,
        candidate_answer=candidate_answer,
        agent_system_prompt=agent_system_prompt.strip(),
        available_tools=available_tools,
    )
    return await structured.ainvoke(prompt)  # type: ignore[return-value]


def judge_version(model: str) -> str:
    """Content hash of the judge — the rubric prompt plus the judge model.

    The judge is part of the measuring instrument: change the rubric or swap the
    model and scores shift, so the version that grades a run is recorded next to
    the prompt version it grades against. Mirrors ``PromptBundle.version``.

    Only the rubric *template* and model are hashed. The agent's system prompt
    and tool list are injected into the judge at runtime but deliberately left
    out: that content is the thing under test, already captured by
    ``prompt_version`` in the run metadata, so folding it in here would just
    couple the judge's identity to the agent's configuration.
    """
    payload = json.dumps(
        {"judge_prompt": _JUDGE_PROMPT, "judge_model": model},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
