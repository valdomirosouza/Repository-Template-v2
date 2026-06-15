"""Versioned, on-disk LLM prompt loading (ADR-0079).

System prompts are externalised from Python into versioned files under the
repository's top-level ``prompts/`` directory (``prompts/<area>/<name>.vN.md``).
Each file carries YAML front-matter (id, version, owner, model, eval_dataset,
supersedes) and a single fenced ``text`` block whose contents are the prompt body.

Loading a prompt by id returns the body **byte-identical** to the former inline
constant, so runtime behaviour is unchanged. See ``loader.py`` for the contract.
"""

from __future__ import annotations

from src.agents.prompts.loader import (
    PromptDefinition,
    PromptError,
    load_prompt,
    load_prompt_definition,
)

__all__ = [
    "PromptDefinition",
    "PromptError",
    "load_prompt",
    "load_prompt_definition",
]
