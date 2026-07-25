"""How retrieved theory is framed to the model, and that the framing is versioned.

Theory retrieved for an earlier position must never reach the model looking like
a description of the position on the board, and every string that does that
labelling has to be part of the hashed prompt bundle.
"""

from langchain_core.messages import HumanMessage

from backend.agent.client import Client
from backend.agent.prompt_bundle import PromptBundle, _version_hash, build_bundle
from backend.agent.tools import Retrieval
from tests.agent.factories import opening_doc

PGN = "1. b4 e5 2. Bb2"
DOCS = "[Document 1: Polish Opening]\n1. b4 grabs queenside space."


def inject(retrieval: Retrieval, docs: str, bundle: PromptBundle | None = None):
    """Run the injection around a single user message and return the added
    context messages."""
    bundle = bundle or build_bundle([])
    messages = Client._inject_position_context(
        [HumanMessage("What is going on here?")], PGN, retrieval, docs, bundle
    )
    return [m.content for m in messages[:-1]]


def test_exact_docs_are_presented_as_the_current_position():
    contexts = inject(
        Retrieval(docs=[opening_doc()], plies_back=0, moves_since=()), DOCS
    )
    docs_message = contexts[-1]
    assert DOCS in docs_message
    assert docs_message == build_bundle([]).docs_preamble.format(docs=DOCS)


def test_ancestor_docs_are_labelled_as_an_earlier_position():
    retrieval = Retrieval(docs=[opening_doc()], plies_back=2, moves_since=("e5", "Bb2"))
    docs_message = inject(retrieval, DOCS)[-1]

    assert DOCS in docs_message
    assert "e5 Bb2" in docs_message  # the moves played since
    assert "2 half-move" in docs_message
    # The exact-match framing must not be reused for it.
    assert docs_message != build_bundle([]).docs_preamble.format(docs=DOCS)
    assert docs_message == build_bundle([]).ancestor_docs_preamble.format(
        docs=DOCS, plies_back=2, moves_since="e5 Bb2"
    )


def test_no_docs_falls_back_regardless_of_distance():
    contexts = inject(Retrieval(docs=[], plies_back=0, moves_since=()), "")
    assert contexts[-1] == build_bundle([]).no_docs_fallback


def test_ancestor_preamble_is_taken_from_the_bundle_not_the_module():
    """The labelling text has to be read off the bundle, so a prompt version
    pins what the model was actually told."""
    bundle = build_bundle([])
    bundle.ancestor_docs_preamble = "SENTINEL {plies_back} {moves_since} {docs}"

    docs_message = inject(
        Retrieval(docs=[opening_doc()], plies_back=1, moves_since=("Bb2",)),
        DOCS,
        bundle,
    )[-1]

    assert docs_message == f"SENTINEL 1 Bb2 {DOCS}"


def test_ancestor_preamble_is_part_of_the_hashed_bundle():
    bundle = build_bundle([])
    changed = build_bundle([])
    changed.ancestor_docs_preamble = "something else entirely"

    assert _version_hash(changed._payload()) != bundle.version
