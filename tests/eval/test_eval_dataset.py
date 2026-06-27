"""CI-safe checks on the eval golden set — no API calls, no cost.

These guard the dataset *contract* (so the harness can rely on it) and, just as
importantly, assert that the set actually exercises the decision boundaries the
metrics are meant to measure. A routing metric over a set with no negative
cases is meaningless; this test fails loudly if the set drifts that way.
"""

import json

from tests.eval.build_dataset import SOURCE, to_jsonl
from tests.eval.dataset import DATASET_PATH, load_records


def test_dataset_is_wellformed():
    records = load_records()
    assert records, "golden set is empty"

    ids = [r.id for r in records]
    assert len(ids) == len(set(ids)), "duplicate record ids"

    for r in records:
        assert r.question, f"{r.id}: empty question"
        assert isinstance(r.expected_tools, list), f"{r.id}: expected_tools not a list"
        assert isinstance(r.in_scope, bool), f"{r.id}: in_scope not a bool"
        assert r.reference_answer, f"{r.id}: empty reference_answer"


def test_dataset_covers_decision_boundaries():
    records = load_records()
    assert any(not r.in_scope for r in records), "no out-of-scope (negative) case"
    assert any(r.expected_tools == [] for r in records), "no no-tool case"
    assert any(r.expected_tools for r in records), "no tool-use case"


def test_jsonl_is_in_sync_with_json():
    """The JSONL is a build artifact of the JSON; fail if it's stale."""
    expected = to_jsonl(json.loads(SOURCE.read_text(encoding="utf-8")))
    actual = DATASET_PATH.read_text(encoding="utf-8")
    assert actual == expected, "eval_set.jsonl is stale; run build_dataset"
