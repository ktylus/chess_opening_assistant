"""Collects the model-facing prompt text and tool descriptions into a single
immutable, content-hashed ``PromptBundle``.
"""

import hashlib
import json

from langchain_core.tools import BaseTool

from backend.agent import prompts, tools
from backend.chess_utils import position_profile


class PromptBundle:
    """An immutable snapshot of every author-written string the model reads."""

    __slots__ = (
        "system_prompt",
        "position_context_template",
        "profile_preamble",
        "docs_preamble",
        "ancestor_docs_preamble",
        "no_docs_fallback",
        "doc_format",
        "profile_text",
        "tool_output_text",
        "tool_descriptions",
        "version",
    )

    def __init__(self, *, tool_descriptions: dict[str, str]):
        self.system_prompt = prompts.SYSTEM_PROMPT
        self.position_context_template = prompts.POSITION_CONTEXT_TEMPLATE
        self.profile_preamble = prompts.PROFILE_PREAMBLE
        self.docs_preamble = prompts.DOCS_PREAMBLE
        self.ancestor_docs_preamble = prompts.ANCESTOR_DOCS_PREAMBLE
        self.no_docs_fallback = prompts.NO_DOCS_FALLBACK
        self.doc_format = prompts.DOC_FORMAT
        self.profile_text = position_profile.model_facing_text()
        self.tool_output_text = tools.model_facing_text()
        self.tool_descriptions = dict(tool_descriptions)
        self.version = _version_hash(self._payload())

    def _payload(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "position_context_template": self.position_context_template,
            "profile_preamble": self.profile_preamble,
            "docs_preamble": self.docs_preamble,
            "ancestor_docs_preamble": self.ancestor_docs_preamble,
            "no_docs_fallback": self.no_docs_fallback,
            "doc_format": self.doc_format,
            "profile_text": self.profile_text,
            "tool_output_text": self.tool_output_text,
            "tool_descriptions": self.tool_descriptions,
        }


def build_bundle(tools: list[BaseTool]) -> PromptBundle:
    """Build a bundle from the prompt text and the given tools' descriptions."""
    tool_descriptions = {t.name: t.description for t in tools}
    return PromptBundle(tool_descriptions=tool_descriptions)


def _version_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest[:12]
