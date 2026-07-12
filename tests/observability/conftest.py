import pytest

from backend.observability import reset_context


@pytest.fixture(autouse=True)
def clean_context():
    """Keep identifiers bound by one test from leaking into the next."""
    reset_context()
    yield
    reset_context()
