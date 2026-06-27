"""Load the eval golden set into typed records.

A record separates three lifecycles (mirrored in the JSON structure):

- ``input``  — what we author: the user prompt + board position.
- ``labels`` — what we author: the answer key the metrics grade against.
- ``output`` — what the *system* produces at run time (response, retrieved
  contexts, tools called). It is never stored in the golden set; the runner
  fills it in by actually running the agent.

This module only deals with the first two.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DATASET_PATH = Path(__file__).parent / "eval_set.jsonl"


@dataclass(frozen=True)
class EvalRecord:
    id: str
    question: str
    pgn: str
    # Ground-truth labels:
    expected_tools: list[str]  # model-chosen tools that *should* fire ([] = none)
    in_scope: bool  # is the position within the assistant's opening scope?
    reference_answer: str  # gold answer, used to assist the rubric judge

    @classmethod
    def from_dict(cls, record: dict) -> "EvalRecord":
        return cls(
            id=record["id"],
            question=record["input"]["question"],
            pgn=record["input"].get("pgn", ""),
            expected_tools=record["labels"]["expected_tools"],
            in_scope=record["labels"]["in_scope"],
            reference_answer=record["labels"]["reference_answer"],
        )


def load_records(path: Path = DATASET_PATH) -> list[EvalRecord]:
    with open(path, encoding="utf-8") as f:
        return [EvalRecord.from_dict(json.loads(line)) for line in f if line.strip()]
