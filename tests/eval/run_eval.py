"""Run the eval as a LangSmith experiment over the uploaded dataset.

This actually calls the agent (Gemini) and the judge (Claude), so it needs API
keys and costs a little per run. It is a script, not a CI test:

    uv run python -m tests.eval.upload_dataset   # once, and after editing the set
    uv run python -m tests.eval.run_eval

For each example LangSmith runs the agent, then scores routing (deterministic)
and answer quality (LLM judge). Results land in LangSmith as an experiment tied
to the dataset version, stamped with the prompt and judge versions under test, so
every run is queryable by exactly what produced it: dataset rows, prompt
elements, judge, and scores. Requires ``LANGSMITH_TRACING=true`` and an API key.
"""

import asyncio
import subprocess

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langsmith import aevaluate

from src.agent.chat_models import ChatRequest, Message, MessageRole
from src.agent.client import MODEL, Client
from tests.eval.metrics import (
    JUDGE_MODEL,
    judge_quality,
    judge_version,
    score_routing,
)
from tests.eval.upload_dataset import DATASET_NAME


def make_judge(model: str = JUDGE_MODEL) -> BaseChatModel:
    return init_chat_model(model=model, model_provider="anthropic")


def make_target(client: Client):
    """The system under test: maps a dataset example's inputs to the agent's
    output. Runs under the experiment's trace, so the assembled system prompt,
    injected context and tool calls are all inspectable per example."""

    async def run_agent(inputs: dict) -> dict:
        request = ChatRequest(
            messages=[Message(role=MessageRole.USER, content=inputs["question"])],
            pgn=inputs.get("pgn", ""),
        )
        response = await client.run(request)
        return {
            "answer": response.text,
            "tool_calls": response.tool_calls,
            "contexts": response.contexts,
        }

    return run_agent


def routing_evaluator(outputs: dict, reference_outputs: dict) -> dict:
    """Deterministic: did the agent fire exactly the tools it should have?"""
    result = score_routing(reference_outputs["expected_tools"], outputs["tool_calls"])
    return {"key": "routing", "score": result.passed}


# Feedback keys are left as unbounded continuous (configured once in the
# workspace, not per-result). A key's config is fixed on first creation, so
# sending bounds in the payload risks an ingest-rejecting mismatch — and because
# run outputs and feedback share one multipart batch, a rejected batch also drops
# the model response. Scores ride the 1-5 rubric; the range is documented on
# QualityScore, not enforced by LangSmith.
def make_quality_evaluator(judge: BaseChatModel):
    """LLM-as-judge over the rubric, returning one feedback per axis plus an
    overall, with the judge's reasoning attached as a comment."""

    async def quality_evaluator(
        inputs: dict, outputs: dict, reference_outputs: dict
    ) -> list[dict]:
        score = await judge_quality(
            judge,
            question=inputs["question"],
            pgn=inputs.get("pgn", ""),
            in_scope=reference_outputs["in_scope"],
            reference_answer=reference_outputs["reference_answer"],
            candidate_answer=outputs["answer"],
        )
        return [
            {"key": "correctness", "score": score.correctness},
            {"key": "completeness", "score": score.completeness},
            {"key": "scope_adherence", "score": score.scope_adherence},
            {
                "key": "quality_overall",
                "score": score.overall,
                "comment": score.reasoning,
            },
        ]

    return quality_evaluator


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


async def main() -> None:
    load_dotenv()
    client = Client()
    judge = make_judge()

    # Run-level provenance: the join keys that let any result be traced back to
    # the exact configuration that produced it (prompt elements, judge, model).
    metadata = {
        "prompt_version": client.prompt_bundle().version,
        "model": MODEL,
        "judge_model": JUDGE_MODEL,
        "judge_version": judge_version(),
        "git_sha": _git_sha(),
    }

    results = await aevaluate(
        make_target(client),
        data=DATASET_NAME,
        evaluators=[routing_evaluator, make_quality_evaluator(judge)],  # type: ignore
        metadata=metadata,
        experiment_prefix="chess-opening",
        # Sequential: keeps within API rate limits and is easy to read in logs.
        max_concurrency=1,
    )
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
