"""Push the local golden set to a versioned LangSmith dataset.

The JSONL in this folder is the authoring surface; LangSmith owns the canonical,
versioned copy that experiments run against. Re-run after editing the set: it
upserts by record id, and every change LangSmith sees becomes a new dataset
version, so each experiment can be pinned to the exact rows it ran on.

    uv run python -m tests.eval.upload_dataset

The dataset mirrors the JSONL's three lifecycles: ``inputs`` is what we author
for the agent (question + position); ``outputs`` is the answer key the metrics
grade against. The system's own output is never stored here — the runner fills
it in by actually running the agent.
"""

import uuid

from dotenv import load_dotenv
from langsmith import Client as LangSmithClient

from tests.eval.dataset import EvalRecord, load_records

DATASET_NAME = "chess-opening-evals"
# Stable namespace so a record id (e.g. "ruy-lopez-1") always maps to the same
# LangSmith example id — that's what makes re-uploads an upsert, not a duplicate.
_ID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000c4e55e7a")


def _example_id(record_id: str) -> uuid.UUID:
    return uuid.uuid5(_ID_NAMESPACE, record_id)


def _to_example(record: EvalRecord) -> dict:
    return {
        "id": _example_id(record.id),
        "inputs": {"question": record.question, "pgn": record.pgn},
        "outputs": {
            "expected_tools": record.expected_tools,
            "in_scope": record.in_scope,
            "reference_answer": record.reference_answer,
        },
        "metadata": {"record_id": record.id},
    }


def main() -> None:
    load_dotenv()
    client = LangSmithClient()

    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        dataset = client.create_dataset(
            DATASET_NAME,
            description="Chess opening assistant golden set (authored in eval_set.jsonl).",
        )

    examples = [_to_example(r) for r in load_records()]
    existing = {e.id for e in client.list_examples(dataset_id=dataset.id)}
    to_update = [e for e in examples if e["id"] in existing]
    to_create = [e for e in examples if e["id"] not in existing]

    if to_create:
        client.create_examples(dataset_id=dataset.id, examples=to_create)
    if to_update:
        client.update_examples(dataset_id=dataset.id, updates=to_update)

    print(
        f"Synced {len(examples)} examples to dataset '{DATASET_NAME}' "
        f"({len(to_create)} created, {len(to_update)} updated)."
    )


if __name__ == "__main__":
    main()
