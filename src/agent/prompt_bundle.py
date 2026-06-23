"""Assembles every model-facing prompt surface into one versioned artifact.

Approach (B): nothing is moved into a stored data file. Tool descriptions stay
as docstrings and are read at runtime via ``tool.description``; the prompt text
stays in ``prompts.py``. ``build_bundle`` collects all of it into an immutable
``PromptBundle`` and derives a content hash, so a single ``version`` id covers
the whole bundle. Attach that id as run metadata (LangSmith) and any tone or
length regression can be attributed to the exact bundle that produced it.

The hash is the source of truth for the version: it can't drift from what runs,
and needs no manual bumping.
"""

import hashlib
import json

from langchain_core.tools import BaseTool

from src.agent import prompts


class PromptBundle:
    """An immutable snapshot of every author-written string the model reads."""

    __slots__ = (
        "system_prompt",
        "position_context_template",
        "profile_preamble",
        "docs_preamble",
        "no_docs_fallback",
        "doc_format",
        "tool_descriptions",
        "version",
    )

    def __init__(self, *, tool_descriptions: dict[str, str]):
        self.system_prompt = prompts.SYSTEM_PROMPT
        self.position_context_template = prompts.POSITION_CONTEXT_TEMPLATE
        self.profile_preamble = prompts.PROFILE_PREAMBLE
        self.docs_preamble = prompts.DOCS_PREAMBLE
        self.no_docs_fallback = prompts.NO_DOCS_FALLBACK
        self.doc_format = prompts.DOC_FORMAT
        self.tool_descriptions = dict(tool_descriptions)
        self.version = _version_hash(self._payload())

    def _payload(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "position_context_template": self.position_context_template,
            "profile_preamble": self.profile_preamble,
            "docs_preamble": self.docs_preamble,
            "no_docs_fallback": self.no_docs_fallback,
            "doc_format": self.doc_format,
            "tool_descriptions": self.tool_descriptions,
        }


def build_bundle(tools: list[BaseTool]) -> PromptBundle:
    """Collect the prompt text plus the agent's tool descriptions into a bundle.

    Tool descriptions are read off the live tool objects, so whatever the agent
    actually sees is what gets hashed.
    """
    tool_descriptions = {t.name: t.description for t in tools}
    return PromptBundle(tool_descriptions=tool_descriptions)


def _version_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest[:12]
