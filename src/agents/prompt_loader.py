"""Deterministic loader for externalised, versioned agent prompts.

Spec:  prompts/README.md (target on-disk layout + front-matter schema)
       docs/ai/prompt-registry.md (authoritative registry)
ADR:   ADR-0079 (Externalise agent prompts)

Prompts live on disk as ``prompts/<area>/<name>.vN.md`` with YAML front-matter
followed by the prompt body wrapped in a single fenced code block. This module
maps a stable ``prompt_id`` to its file, strips the front-matter and the fence,
and returns the prompt body **byte-for-byte** identical to the constant that used
to be inline in Python — so externalisation is behaviour-preserving.

The body is wrapped in a ``` fenced block on disk because the repo's Markdown
formatter would otherwise reflow indentation and blank lines; content inside a
fenced block is preserved verbatim by the formatter. The closing fence always
sits on its own line, so the captured block content carries exactly one trailing
newline introduced by that layout, which is removed on load. Each prompt file
encodes a deliberate blank line before the closing fence when (and only when) the
original constant ended with a trailing newline.

No network access and no I/O beyond reading the bundled prompt files. Results are
cached in-process keyed by ``prompt_id``.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

# Repository root is three levels up from this file: src/agents/prompt_loader.py.
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

# Stable prompt id -> path (relative to the prompts/ directory). Adding a prompt
# means registering it here and in docs/ai/prompt-registry.md.
_PROMPT_FILES: dict[str, str] = {
    "harness.planner": "harness/planner.v1.md",
    # evaluator bumped to v2 (ADR-0080): adds the gated `groundedness` dimension.
    # evaluator.v1.md is retained on disk for rollback history only.
    "harness.evaluator": "harness/evaluator.v2.md",
    "orchestrator.reason": "agent-orchestrator/reason.v1.md",
}

# Front-matter delimited by lines of exactly '---', at the very start of the file.
_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# The first fenced code block (``` optionally followed by a language tag).
_FENCE_RE = re.compile(r"```[A-Za-z0-9_-]*\n(?P<body>.*?)```", re.DOTALL)


class PromptNotFoundError(KeyError):
    """Raised when an unknown ``prompt_id`` is requested."""


def _extract_body(raw: str, prompt_id: str) -> str:
    """Strip front-matter and the fenced wrapper, returning the prompt body.

    Removes the single trailing newline the fenced-block layout always appends
    (the closing fence on its own line), preserving the original constant exactly.
    """
    without_front_matter = _FRONT_MATTER_RE.sub("", raw, count=1)
    match = _FENCE_RE.search(without_front_matter)
    if match is None:
        raise ValueError(
            f"Prompt '{prompt_id}' has no fenced prompt body — "
            "the body must be wrapped in a ``` code block."
        )
    body = match.group("body")
    if body.endswith("\n"):
        body = body[:-1]
    return body


@cache
def load_prompt(prompt_id: str) -> str:
    """Return the prompt body for ``prompt_id``, byte-for-byte.

    The id maps deterministically to ``prompts/<area>/<file>.vN.md``. The YAML
    front-matter and the fenced-block wrapper are stripped; the returned string is
    identical to the prompt constant that previously lived inline in Python.

    Args:
        prompt_id: A registered prompt id, e.g. ``"harness.planner"``.

    Returns:
        The prompt body text.

    Raises:
        PromptNotFoundError: if ``prompt_id`` is not registered.
        FileNotFoundError: if the registered prompt file is missing.
        ValueError: if the file has no fenced prompt body.
    """
    try:
        rel_path = _PROMPT_FILES[prompt_id]
    except KeyError as exc:
        known = ", ".join(sorted(_PROMPT_FILES))
        raise PromptNotFoundError(f"Unknown prompt id '{prompt_id}'. Known ids: {known}.") from exc

    raw = (_PROMPTS_DIR / rel_path).read_text(encoding="utf-8")
    return _extract_body(raw, prompt_id)
