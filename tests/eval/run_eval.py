"""Run the eval as a LangSmith experiment over the uploaded dataset.

This actually calls the agent (Gemini) and the judge (Claude), so it needs API
keys and costs a little per run. It is a script, not a CI test:

    uv run python -m tests.eval.run_eval

There's no separate upload step to remember: the runner upserts the LangSmith
dataset (idempotent) from the authored ``eval_set.json`` before every run, so the
experiment always grades against the current golden set. ``tests.eval.sync`` does
the same upsert on its own, for pushing the dataset without paying for a full
eval.

For each example LangSmith runs the agent, then scores tool usage (deterministic)
and answer quality (LLM judge). Results land in LangSmith as an experiment
stamped with everything that shaped the answers: the prompt, dataset and judge
hashes, the commit, and the engine and retrieval config behind the tools. The
same ``prompt_version`` and ``git_sha`` are stamped on the wide event each live
request logs, so an experiment and a complaint about production can be joined.

Two inputs resist being pinned, and the metadata says so rather than implying
otherwise: Stockfish is searched on wall-clock time, and the Lichess masters
database is live. Identical code can therefore score differently on different
days. Requires ``LANGSMITH_TRACING=true`` and an API key.
"""

import asyncio

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langsmith import aevaluate

from backend.agent.chat_models import ChatRequest, Message, MessageRole
from backend.agent.client import MODEL, Client
from backend.agent.tools import tool_config
from backend.observability.provenance import git_sha, is_dirty
from tests.eval.dataset import dataset_version
from tests.eval.metrics import (
    judge_quality,
    judge_version,
    score_tool_usage,
)
from tests.eval.sync import DATASET_NAME, sync_dataset

# The judge shares the agent's model to keep dev runs cheap. That costs the
# cross-provider guarantee: a model shown its own output grades it generously, so
# quality scores read optimistically. The bias is recorded per run as
# ``judge_is_agent_model`` rather than left for a reader to infer from two ids
# that happen to match, and it is why absolute scores here mean less than the
# movement between runs.
JUDGE_MODEL = "gemini-3.1-flash-lite"
JUDGE_PROVIDER = "google_genai"


def make_judge(model: str = JUDGE_MODEL) -> BaseChatModel:
    return init_chat_model(model=model, model_provider=JUDGE_PROVIDER)


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
            # Per-example, not run-level: the alias in the run metadata names a
            # policy, and the provider is free to serve different weights under
            # it -- in principle between one example and the next.
            "model_version": response.model_version,
        }

    return run_agent


def tool_usage_evaluator(outputs: dict, reference_outputs: dict) -> dict:
    """Deterministic: did the agent fire every tool it was expected to?"""
    result = score_tool_usage(
        reference_outputs["expected_tools"], outputs["tool_calls"]
    )
    return {"key": "tool_usage", "score": result.passed}


# Feedback keys are left as unbounded continuous (configured once in the
# workspace, not per-result). A key's config is fixed on first creation, so
# sending bounds in the payload risks an ingest-rejecting mismatch — and because
# run outputs and feedback share one multipart batch, a rejected batch also drops
# the model response. Scores ride the 1-5 rubric; the range is documented on
# QualityScore, not enforced by LangSmith.
def _format_tools(tool_descriptions: dict[str, str]) -> str:
    """Render the agent's live tool descriptions as a list for the judge prompt.

    Reads from the prompt bundle's ``tool_descriptions`` — the same dict the
    agent is actually built from — so the judge can never be told about a tool
    the agent doesn't have, or miss one it does.
    """
    return "\n".join(
        f"- {name}: {desc.strip()}" for name, desc in tool_descriptions.items()
    )


def make_quality_evaluator(
    judge: BaseChatModel, agent_system_prompt: str, available_tools: str
):
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
            agent_system_prompt=agent_system_prompt,
            available_tools=available_tools,
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


def _temperature(model: BaseChatModel) -> float | None:
    """Return the temperature the model is configured with, or ``None`` if it
    was never set and the provider's own default therefore applied."""
    return getattr(model, "temperature", None)


async def main() -> None:
    load_dotenv()

    if is_dirty():
        print(
            f"WARNING: uncommitted changes. This run is stamped {git_sha()}; its "
            "prompt_version cannot be resolved back to any commit."
        )

    # Keep the LangSmith dataset in lockstep with the authored source before the
    # run. The upsert always fires (it's idempotent), so LangSmith can never
    # silently drift from what's in eval_set.json — no separate step to forget.
    created, updated = sync_dataset()
    print(f"Synced dataset '{DATASET_NAME}': {created} created, {updated} updated.")

    client = Client()
    judge = make_judge()

    # The judge grades against what the agent was actually given: its system
    # prompt (the real scope rules) and its live tool set (so engine/explorer
    # output isn't mistaken for hallucination). Both come from the same bundle.
    bundle = client.prompt_bundle()
    agent_system_prompt = bundle.system_prompt
    available_tools = _format_tools(bundle.tool_descriptions)

    # Run-level provenance: the join keys that let any result be traced back to
    # the configuration that produced it. The version fields are hashes, and a
    # hash is only resolvable through the repository, so git_sha is what makes
    # the rest of this mean anything -- hence it names a dirty tree as dirty.
    # tool_config covers what no commit can pin: an engine binary resolved from
    # the environment and a live external opening database.
    #
    # A null temperature is not a missing value: it records that we set none and
    # ran on the provider's default, which is itself free to move between runs.
    metadata = {
        "prompt_version": bundle.version,
        "model": MODEL,
        "agent_temperature": _temperature(client.model),
        "judge_model": JUDGE_MODEL,
        "judge_version": judge_version(JUDGE_MODEL),
        "judge_temperature": _temperature(judge),
        "judge_is_agent_model": JUDGE_MODEL == MODEL,
        "dataset_version": dataset_version(),
        "git_sha": git_sha(),
        **tool_config(),
    }

    results = await aevaluate(
        make_target(client),
        data=DATASET_NAME,
        evaluators=[
            tool_usage_evaluator,
            make_quality_evaluator(judge, agent_system_prompt, available_tools),  # type: ignore
        ],
        metadata=metadata,
        experiment_prefix="chess-opening",
        # Sequential: keeps within API rate limits and is easy to read in logs.
        max_concurrency=1,
    )
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
