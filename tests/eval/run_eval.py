"""Run the eval as a LangSmith experiment over the uploaded dataset.

This actually calls the agent (Gemini) and the judge (Claude), so it needs API
keys and costs a little per run. It is a script, not a CI test:

    uv run python -m tests.eval.run_eval

There's no separate build/upload step to remember: the runner rebuilds
``eval_set.jsonl`` whenever the authored ``eval_set.json`` has changed and
upserts the LangSmith dataset (idempotent) before every run, so the experiment
always grades against the current golden set. ``tests.eval.sync`` does the same
build+upsert on its own, for pushing the dataset without paying for a full eval.

For each example LangSmith runs the agent, then scores tool usage (deterministic)
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
    judge_quality,
    judge_version,
    score_tool_usage,
)
from tests.eval.sync import DATASET_NAME, rebuild_if_stale, sync_dataset

# A Claude judge against the Gemini agent under test, deliberately cross-provider
# to limit self-preference bias. Lives beside the agent's MODEL it pairs against.
JUDGE_MODEL = "claude-opus-4-8"

# The judge is pinned to 0 so grading is as reproducible as possible: score drift
# between runs should come from the agent's behaviour, not the judge's sampling.
# The agent itself is left on its production (provider-default) temperature so the
# eval grades the system we actually ship — see the metadata stamped below.
JUDGE_TEMPERATURE = 0


def make_judge(model: str = JUDGE_MODEL) -> BaseChatModel:
    return init_chat_model(
        model=model, model_provider="anthropic", temperature=JUDGE_TEMPERATURE
    )


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


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


async def main() -> None:
    load_dotenv()

    # Keep the LangSmith dataset in lockstep with the authored source before the
    # run. The JSONL is rebuilt only when eval_set.json changed, but the upsert
    # always fires (it's idempotent), so LangSmith can never silently drift from
    # what's on disk — no separate build/upload step to forget.
    if rebuild_if_stale():
        print("eval_set.json changed; rebuilt eval_set.jsonl.")
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
    # the exact configuration that produced it (prompt elements, judge, model).
    metadata = {
        "prompt_version": bundle.version,
        "model": MODEL,
        # The agent isn't pinned; it runs on the provider default (what we ship).
        # Recorded explicitly so a run's sampling config is part of its provenance.
        "agent_temperature": "provider default",
        "judge_model": JUDGE_MODEL,
        "judge_version": judge_version(JUDGE_MODEL),
        "judge_temperature": JUDGE_TEMPERATURE,
        "git_sha": _git_sha(),
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
