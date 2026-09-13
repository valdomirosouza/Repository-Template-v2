"""Unit tests for the topic-contract governance gate (W11-T3, issue #348).

Covers the five rules of ``evaluate`` with synthetic inputs, the three literal scanners, and one
offline run against the real repository (registry, contract and code must agree on ``main``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_topic_contract as tc  # noqa: E402

pytestmark = pytest.mark.unit


def _registry(*topics: tuple[str, str], services: list[dict] | None = None) -> dict:
    return {
        "topics": [{"name": n, "lifecycle": lc} for n, lc in topics],
        "services": services or [],
    }


def _asyncapi(**channels: str) -> dict:
    return {"channels": {name: {"x-stability": stab} for name, stab in channels.items()}}


# ------------------------------------------------------------------------ rules


def test_consistent_inputs_pass():
    rep = tc.evaluate(
        registry=_registry(("a.b.c", "active"), ("x.y.z", "planned")),
        asyncapi=_asyncapi(**{"a.b.c": "stable", "x.y.z": "planned"}),
        literals=[tc.Literal("a.b.c", "src/x.py:1")],
    )
    assert rep.ok, rep
    assert rep.warnings == []


def test_e1_registry_and_contract_must_match_both_ways():
    rep = tc.evaluate(
        registry=_registry(("only.in.registry", "active")),
        asyncapi=_asyncapi(**{"only.in.contract": "stable"}),
        literals=[],
    )
    assert not rep.ok
    assert any("only.in.registry" in e and e.startswith("E1") for e in rep.errors)
    assert any("only.in.contract" in e and e.startswith("E1") for e in rep.errors)


def test_e2_code_literal_must_be_registered():
    rep = tc.evaluate(
        registry=_registry(("a.b.c", "active")),
        asyncapi=_asyncapi(**{"a.b.c": "stable"}),
        literals=[tc.Literal("rogue.topic.name", "src/rogue.py:7")],
    )
    assert [e for e in rep.errors if e.startswith("E2")] == [
        "E2 code publishes/consumes unregistered topic 'rogue.topic.name' (src/rogue.py:7)"
    ]


def test_e3_lifecycle_must_agree_with_stability():
    rep = tc.evaluate(
        registry=_registry(("a.b.c", "planned")),
        asyncapi=_asyncapi(**{"a.b.c": "stable"}),
        literals=[],
    )
    assert len(rep.errors) == 1 and rep.errors[0].startswith("E3")


def test_e3_beta_is_acceptable_for_active():
    rep = tc.evaluate(
        registry=_registry(("a.b.c", "active")),
        asyncapi=_asyncapi(**{"a.b.c": "beta"}),
        literals=[tc.Literal("a.b.c", "src/x.py:1")],
    )
    assert rep.ok, rep


def test_unknown_lifecycle_is_an_error():
    rep = tc.evaluate(
        registry=_registry(("a.b.c", "whatever")),
        asyncapi=_asyncapi(**{"a.b.c": "stable"}),
        literals=[tc.Literal("a.b.c", "src/x.py:1")],
    )
    assert any("unknown lifecycle" in e for e in rep.errors)


def test_e4_service_declarations_must_be_registered():
    rep = tc.evaluate(
        registry=_registry(
            ("a.b.c", "active"),
            services=[{"name": "svc", "publishes": ["a.b.c"], "subscribes": ["nope.nope.nope"]}],
        ),
        asyncapi=_asyncapi(**{"a.b.c": "stable"}),
        literals=[],
    )
    assert [e for e in rep.errors if e.startswith("E4")] == [
        "E4 service 'svc' subscribes unregistered topic 'nope.nope.nope'"
    ]
    # a.b.c is published by a declared service, so no W1 warning
    assert rep.warnings == []


def test_w1_active_topic_without_publisher_warns_but_passes():
    rep = tc.evaluate(
        registry=_registry(("a.b.c", "active")),
        asyncapi=_asyncapi(**{"a.b.c": "stable"}),
        literals=[],
    )
    assert rep.ok
    assert len(rep.warnings) == 1 and "a.b.c" in rep.warnings[0]


def test_render_marks_errors_for_ci():
    rep = tc.Report(errors=["E1 boom"], warnings=["W1 meh"])
    text = tc.render(rep, n_topics=1, n_literals=0)
    assert "::error::E1 boom" in text and "WARN W1 meh" in text and "RESULT: FAIL" in text


# ------------------------------------------------------------------------ scanners


def test_scan_python_finds_publish_topic_and_dlq_setting(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(
        'await broker.publish(\n    "domain.request.created", env, key=k\n)\n'
        'TOPIC = "domain.request.created"\n'
        'kafka_dlq_topic: str = "domain.request.dlq"\n',
        encoding="utf-8",
    )
    found = {(lit.topic, lit.where.split(":")[-1]) for lit in tc.scan_python(src)}
    assert ("domain.request.created", "1") in found
    assert ("domain.request.created", "4") in found
    assert ("domain.request.dlq", "5") in found


def test_scan_java_and_go_defaults(tmp_path: Path):
    j = tmp_path / "svc" / "src" / "main" / "resources"
    j.mkdir(parents=True)
    (j / "application.yml").write_text(
        "topics:\n  request-created: ${KAFKA_TOPIC_REQUEST_CREATED:request.created.v1}\n",
        encoding="utf-8",
    )
    g = tmp_path / "worker"
    g.mkdir()
    (g / "config.go").write_text(
        'x := getEnv("KAFKA_TOPIC_EVENT_PROCESSED", "event.processed.v1")\n', encoding="utf-8"
    )
    (g / "config_test.go").write_text('getEnv("KAFKA_TOPIC_X", "ignored.in.tests")\n')
    topics = {lit.topic for lit in tc.scan_java(tmp_path) + tc.scan_go(tmp_path)}
    assert topics == {"request.created.v1", "event.processed.v1"}


# ------------------------------------------------------------------------ real tree


def test_real_repository_is_consistent():
    """The registry, the contract and the code agree on main (the W11-T2 fix)."""
    rep = tc.evaluate(
        registry=tc.load_registry(),
        asyncapi=tc.load_asyncapi(),
        literals=tc.scan_code(),
    )
    assert rep.ok, "\n".join(rep.errors)
