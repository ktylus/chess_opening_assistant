import pytest

from tests.eval.metrics import QualityScore
from tests.eval.run_eval import make_quality_evaluator


@pytest.mark.parametrize("passed", [True, False])
@pytest.mark.parametrize("contexts", [[], ["Theory before 3.d4"]])
async def test_retrieval_feedback_is_always_reported_separately(
    monkeypatch, passed, contexts
):
    async def fake_judge_quality(*args, **kwargs):
        return QualityScore(
            correctness=5,
            completeness=4,
            scope_adherence=3,
            reasoning="Quality explanation",
            no_retrieval_references=passed,
            retrieval_reference_reasoning="Retrieval explanation",
        )

    monkeypatch.setattr("tests.eval.run_eval.judge_quality", fake_judge_quality)
    evaluator = make_quality_evaluator(None, "Instructions", "Tools")
    feedback = await evaluator(
        {"question": "What is the opening?"},
        {"answer": "Candidate answer", "contexts": contexts},
        {"in_scope": True, "reference_answer": "The Scotch"},
    )
    by_key = {item["key"]: item for item in feedback}
    assert by_key["no_retrieval_references"] == {
        "key": "no_retrieval_references",
        "score": passed,
        "comment": "Retrieval explanation",
    }
    assert by_key["quality_overall"]["score"] == 4
