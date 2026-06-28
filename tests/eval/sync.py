"""Push the authored golden set from ``eval_set.json`` into LangSmith.

The records are loaded into memory (see ``dataset.load_records``) and upserted
into a versioned LangSmith dataset, the canonical copy experiments run against.
The push upserts by record id, so every change becomes a new dataset version and
each experiment can be pinned to the exact rows it ran on.

The dataset mirrors the record's three lifecycles: ``inputs`` is what we author
for the agent (question + position); ``outputs`` is the answer key the metrics
grade against. The system's own output is never stored here — the runner fills
it in by actually running the agent.

``run_eval`` calls ``sync_dataset`` before every run, so there's normally no need
to run this by hand. The ``main`` below stays for pushing the dataset without
paying for a full eval (e.g. while editing the set).

    uv run python -m tests.eval.sync
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


def sync_dataset(client: LangSmithClient | None = None) -> tuple[int, int]:
    """Upsert the local golden set into LangSmith. Returns (created, updated).

    The upsert is idempotent — keyed on the stable example id — so calling this
    when nothing changed is a cheap no-op diff. That's what lets ``run_eval``
    call it unconditionally and trust LangSmith to mirror the authored source.
    """
    if client is None:
        client = LangSmithClient()

    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        dataset = client.create_dataset(
            DATASET_NAME,
            description="Chess opening assistant golden set (authored in eval_set.json).",
        )

    examples = [_to_example(r) for r in load_records()]
    existing = {e.id for e in client.list_examples(dataset_id=dataset.id)}
    to_update = [e for e in examples if e["id"] in existing]
    to_create = [e for e in examples if e["id"] not in existing]

    if to_create:
        client.create_examples(dataset_id=dataset.id, examples=to_create)
    if to_update:
        client.update_examples(dataset_id=dataset.id, updates=to_update)

    return len(to_create), len(to_update)


def main() -> None:
    load_dotenv()
    created, updated = sync_dataset()
    print(
        f"Synced examples to dataset '{DATASET_NAME}' "
        f"({created} created, {updated} updated)."
    )


if __name__ == "__main__":
    main()
