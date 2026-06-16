"""Synchronous loader for versioned, on-disk LLM prompts (ADR-0079).

A prompt is production configuration that changes model behaviour, so it is
versioned on disk like code/config: ``prompts/<area>/<name>.vN.md``. Each file
has YAML front-matter and a single fenced ``text`` block holding the prompt body.

Design constraints
------------------
* **Byte-identical body.** The returned body must equal the former inline Python
  constant exactly, so behaviour is unchanged. The body lives inside a fenced
  code block precisely so the repository's Markdown formatter cannot reflow it
  (alignment, indentation and ``{threshold}`` / ``{{`` / ``}}`` placeholders are
  preserved verbatim).
* **No new dependency.** PyYAML is not a declared runtime dependency, so the
  simple ``key: value`` front-matter is parsed with the standard library only.
* **Synchronous.** Both call sites (evaluator, orchestrator) read the prompt once
  per call on the hot path's owning object; file I/O is local and tiny. Keeping
  it synchronous avoids changing the async signatures of the callers.

This module is import-safe and has no side effects at import time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Repository-root ``prompts/`` directory: src/agents/prompts/loader.py → repo root.
_PROMPTS_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "prompts"

# id → path under ``prompts/``. Adding a prompt is a one-line registration here.
_PROMPT_PATHS: Final[dict[str, str]] = {
    "harness.evaluator": "evaluator/evaluate.v2.md",
    "orchestrator.reason": "agent-orchestrator/reason.v1.md",
}

# Required front-matter keys (prompts/README.md schema).
_REQUIRED_FRONT_MATTER: Final[frozenset[str]] = frozenset(
    {"id", "version", "owner", "model", "eval_dataset", "supersedes"}
)

_FRONT_MATTER_RE: Final[re.Pattern[str]] = re.compile(
    r"\A---\n(?P<front>.*?)\n---\n(?P<rest>.*)\Z",
    re.DOTALL,
)
# Captures the contents of the first ```text fenced block (the prompt body).
_BODY_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"```text\n(?P<body>.*?)\n```",
    re.DOTALL,
)


class PromptError(ValueError):
    """Raised when a prompt cannot be located, parsed, or validated."""


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    """A parsed prompt: validated front-matter plus the verbatim body."""

    id: str
    version: str
    owner: str
    model: str
    eval_dataset: str
    supersedes: str | None
    body: str


def _parse_front_matter(raw: str, *, source: str) -> dict[str, str]:
    """Parse simple ``key: value`` YAML front-matter with the stdlib only.

    Only flat scalar mappings are supported (which is all the schema needs).
    Values are stripped; surrounding single/double quotes are removed.
    """
    data: dict[str, str] = {}
    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise PromptError(f"{source}: malformed front-matter line {lineno}: {line!r}")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key] = value
    return data


def _read_definition(prompt_id: str) -> PromptDefinition:
    rel = _PROMPT_PATHS.get(prompt_id)
    if rel is None:
        raise PromptError(f"unknown prompt id: {prompt_id!r} (not in registry)")

    path = _PROMPTS_DIR / rel
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptError(f"prompt file missing for {prompt_id!r}: {path}") from exc

    fm_match = _FRONT_MATTER_RE.match(text)
    if fm_match is None:
        raise PromptError(f"{path}: missing or malformed YAML front-matter")

    front = _parse_front_matter(fm_match.group("front"), source=str(path))
    missing = _REQUIRED_FRONT_MATTER - front.keys()
    if missing:
        raise PromptError(f"{path}: front-matter missing keys: {sorted(missing)}")

    declared_id = front["id"]
    if declared_id != prompt_id:
        raise PromptError(
            f"{path}: front-matter id {declared_id!r} does not match registry id {prompt_id!r}"
        )

    body_match = _BODY_FENCE_RE.search(fm_match.group("rest"))
    if body_match is None:
        raise PromptError(f"{path}: no ```text fenced prompt body found")

    # Fence content ends just before the closing fence; restore the single trailing
    # newline that delimits the last body line so callers get the verbatim block.
    body = body_match.group("body") + "\n"

    supersedes_raw = front["supersedes"]
    supersedes = None if supersedes_raw.lower() in {"null", "none", ""} else supersedes_raw

    return PromptDefinition(
        id=declared_id,
        version=front["version"],
        owner=front["owner"],
        model=front["model"],
        eval_dataset=front["eval_dataset"],
        supersedes=supersedes,
        body=body,
    )


def load_prompt_definition(prompt_id: str) -> PromptDefinition:
    """Load and validate a prompt, returning its metadata and verbatim body."""
    return _read_definition(prompt_id)


def load_prompt(prompt_id: str, *, strip_trailing_newline: bool = False) -> str:
    """Return the prompt body for ``prompt_id``, byte-identical to the old inline string.

    The fenced body always carries one trailing newline. The former evaluator
    constant ended in ``\\n``; the former orchestrator base string did not. Pass
    ``strip_trailing_newline=True`` to drop exactly that final newline so the
    orchestrator base prompt matches its previous value before dynamic blocks are
    appended.
    """
    body = _read_definition(prompt_id).body
    if strip_trailing_newline and body.endswith("\n"):
        body = body[:-1]
    return body
