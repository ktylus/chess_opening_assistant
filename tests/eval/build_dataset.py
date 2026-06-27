"""Convert the hand-authored ``eval_set.json`` into ``eval_set.jsonl``.

The JSON array is the authoring surface (easy to edit by hand); the JSONL file
is the build artifact the eval harness consumes — one record per line, which
diffs cleanly in git and streams row-by-row.

Run with:  ``uv run python -m tests.eval.build_dataset``
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "eval_set.json"
TARGET = HERE / "eval_set.jsonl"


def to_jsonl(records: list[dict]) -> str:
    """Serialize records to JSONL text (trailing newline, stable key order)."""
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )


def main() -> None:
    records = json.loads(SOURCE.read_text(encoding="utf-8"))
    TARGET.write_text(to_jsonl(records), encoding="utf-8")
    print(f"Wrote {len(records)} records to {TARGET}")


if __name__ == "__main__":
    main()
