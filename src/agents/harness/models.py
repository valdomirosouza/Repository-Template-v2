"""Typed domain models for the multi-agent harness.

Spec: specs/ai/harness-design.md
ADR:  ADR-0014 (Multi-Agent Harness Strategy)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class TaskBrief:
    """Entry point for every harness invocation — the raw user request.

    Kept deliberately thin: 1-4 sentences. The Planner expands it into
    a full ProductSpec. All fields are PII-masked before leaving Perception.
    """

    task_id: str
    description: str
    complexity: Literal["low", "medium", "high"] = "medium"
    trace_id: str | None = None
    correlation_id: str | None = None
    success_criteria: list[str] | None = None


@dataclass
class SprintContract:
    """Negotiated agreement between Generator and Evaluator before implementation.

    Spec: specs/ai/harness-design.md §2 (Sprint Contract Schema)
    Invariants:
    - Each success_criteria item is independently testable and binary.
    - Contract is immutable once both agents confirm it.
    """

    sprint_id: str
    objectives: list[str]
    success_criteria: list[str]
    correlation_id: str | None = None


@dataclass
class ProductSpec:
    """Structured output from the PlannerAgent.

    Spec: specs/ai/harness-design.md §1.1
    """

    task_id: str
    detailed_description: str
    sprint_contracts: list[SprintContract]
    ai_feature_opportunities: list[str] = field(default_factory=list)


@dataclass
class GeneratorArtifact:
    """Output produced by GeneratorAgent for a single sprint.

    Spec: specs/ai/harness-design.md §1.2
    Invariant: all content in `outputs` has been PII-masked before handoff.
    """

    sprint_id: str
    outputs: dict[str, str] = field(default_factory=dict)
    commit_hash: str | None = None


@dataclass
class EvaluatorScore:
    """Quality assessment from EvaluatorAgent.

    Spec: specs/ai/harness-design.md §1.3
    Dimensions are each scored 0.0-1.0. `passed` is True only when all
    dimensions meet or exceed settings.harness_evaluator_pass_threshold.
    """

    sprint_id: str
    quality: float
    originality: float
    craft: float
    functionality: float
    passed: bool
    feedback: str
    retry_required: bool
    iteration: int = 1

    @property
    def average(self) -> float:
        return (self.quality + self.originality + self.craft + self.functionality) / 4


@dataclass
class ContextSnapshot:
    """Structured handoff payload for context resets between agents.

    Spec: specs/ai/harness-design.md §4 (Structured Handoff Model)
    Invariant: masked_state must never contain raw PII — caller is responsible
    for running pii_filter before passing masked_state here.
    """

    agent_id: str
    created_at: str
    task_id: str
    last_sprint_id: str | None = None
    key_decisions: list[str] = field(default_factory=list)
    masked_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessResult:
    """Aggregate result returned by HarnessCoordinator.run().

    Spec: specs/ai/harness-design.md §1.4
    """

    task_id: str
    mode: Literal["solo", "simplified", "full"]
    total_iterations: int
    artifacts: list[GeneratorArtifact] = field(default_factory=list)
    final_score: EvaluatorScore | None = None
    escalated_to_hitl: bool = False
    total_cost_usd: float | None = None
    correlation_id: str | None = None


@dataclass
class DecisionPoint:
    """A recorded branching decision made during sprint execution.

    Spec: specs/ai/harness-design.md §9.1
    """

    decision_point: str
    options_considered: list[str]
    option_chosen: str
    rationale: str


@dataclass
class PatchProposal:
    """LLM self-reflection output proposing an alternative approach after repeated failures.

    Spec: specs/ai/harness-design.md §9.2
    """

    sprint_id: str
    iteration: int
    previous_approach_summary: str
    proposed_alternative: str
    reasoning: str


@dataclass
class ExecutionSummary:
    """Full record of a sprint's execution history — logged and attached to HITL escalations.

    Spec: specs/ai/harness-design.md §9.3
    """

    task_id: str
    sprint_id: str
    total_iterations: int
    failures: list[str]
    patch_proposals_applied: int
    final_score: EvaluatorScore | None
    decisions: list[DecisionPoint]
    generated_at: str
    correlation_id: str | None = None
