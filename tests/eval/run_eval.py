"""Run the agent over the golden set and report eval metrics.

This actually calls the agent (Gemini) and the judge, so it needs API keys and
costs a little per run. It is a script, not a CI test:

    uv run python -m tests.eval.run_eval

For each record it runs the agent, then scores routing (deterministic) and
answer quality (LLM judge). Results are printed as a table and written to
``tests/eval/results.jsonl`` for the README.
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from src.agent.chat_models import ChatRequest, Message, MessageRole
from src.agent.client import Client
from tests.eval.dataset import EvalRecord, load_records
from tests.eval.metrics import (
    QualityScore,
    RoutingResult,
    judge_quality,
    score_routing,
)

RESULTS_PATH = Path(__file__).parent / "results.jsonl"

# A Claude judge against the Gemini agent under test, deliberately cross-provider
# to limit self-preference bias).
JUDGE_MODEL = "claude-sonnet-4-6"


def make_judge(model: str = JUDGE_MODEL) -> BaseChatModel:
    return init_chat_model(model=model, model_provider="anthropic")


@dataclass
class RecordResult:
    id: str
    answer: str
    routing: RoutingResult
    quality: QualityScore


async def evaluate_record(client: Client, judge, record: EvalRecord) -> RecordResult:
    chat_request = ChatRequest(
        messages=[Message(role=MessageRole.USER, content=record.question)],
        pgn=record.pgn,
    )
    response = await client.run(chat_request)
    routing = score_routing(record.expected_tools, response.tool_calls)
    quality = await judge_quality(judge, record, response.text)
    return RecordResult(
        id=record.id, answer=response.text, routing=routing, quality=quality
    )


def report(results: list[RecordResult]) -> None:
    print(f"\n{'id':<16} {'routing':<9} {'correct':<8} {'complete':<9} {'scope':<6}")
    print("-" * 50)
    for r in results:
        routing = "PASS" if r.routing.passed else "FAIL"
        print(
            f"{r.id:<16} {routing:<9} {r.quality.correctness:<8} "
            f"{r.quality.completeness:<9} {r.quality.scope_adherence:<6}"
        )
    print("-" * 50)
    routing_acc = mean(1.0 if r.routing.passed else 0.0 for r in results)
    print(f"Routing accuracy:      {routing_acc:.0%}")
    print(
        f"Avg correctness:       {mean(r.quality.correctness for r in results):.2f}/5"
    )
    print(
        f"Avg completeness:      {mean(r.quality.completeness for r in results):.2f}/5"
    )
    print(
        f"Avg scope adherence:   {mean(r.quality.scope_adherence for r in results):.2f}/5"
    )


def save(results: list[RecordResult]) -> None:
    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        for r in results:
            row = {
                "id": r.id,
                "answer": r.answer,
                "routing": asdict(r.routing),
                "quality": {**r.quality.model_dump(), "overall": r.quality.overall},
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote results to {RESULTS_PATH}")


async def main() -> None:
    records = load_records()
    client = Client()
    judge = make_judge()
    # Sequential: keeps within API rate limits and is easy to read in logs.
    results = [await evaluate_record(client, judge, r) for r in records]
    report(results)
    save(results)


if __name__ == "__main__":
    asyncio.run(main())
