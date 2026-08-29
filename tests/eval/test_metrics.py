from tests.eval.metrics import score_tool_usage


def test_tool_usage_requires_exact_tool_set():
    assert score_tool_usage(["stockfish", "lichess"], ["lichess", "stockfish"]).passed
    assert not score_tool_usage(["stockfish", "lichess"], ["stockfish"]).passed
    assert not score_tool_usage(["stockfish"], ["stockfish", "lichess"]).passed
    assert not score_tool_usage([], ["stockfish"]).passed
