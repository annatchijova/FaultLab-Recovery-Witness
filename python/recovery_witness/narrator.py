"""Narration-only layer over a sealed case file.

This module never influences the sealed decision. It reads a
``sealed-case-file.v1`` envelope that was already produced and sealed by
``harness.build_case_file`` and turns it into prose. The narrator backend is
swappable; swapping it must change only the prose, never the sealed payload
or its digest. See docs/investigator-agent-design.md.
"""

from typing import Any, Callable, Mapping

NARRATION_SCHEMA_VERSION = "case-narrative.v1"
_HIDDEN_KEYS = frozenset({"fault", "injected_fault", "oracle", "oracle_truth"})

Narrator = Callable[[str], str]


def _contains_hidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _HIDDEN_KEYS or _contains_hidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_hidden_key(child) for child in value)
    return False


def build_narration_summary(case_file: Mapping[str, Any]) -> dict[str, Any]:
    """Extract a read-only narration summary from a sealed case file.

    Raises if the envelope is not sealed or carries hidden oracle data. This
    check is defense in depth: the upstream investigator and harness boundary
    should already make a hidden key unreachable here.
    """

    if not isinstance(case_file, Mapping) or case_file.get("schema_version") != "sealed-case-file.v1":
        raise ValueError("narrator requires a sealed-case-file.v1 envelope")
    payload = case_file.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("sealed case file is missing its payload")
    if _contains_hidden_key(payload):
        raise ValueError("sealed payload contains hidden oracle data")

    bench_assessment = payload.get("bench_assessment") or {}
    return {
        "case_id": payload.get("case_id"),
        "mechanic_observations": tuple(
            observation.get("text")
            for observation in payload.get("observations", [])
            if observation.get("source") == "mechanic"
        ),
        "hypotheses": payload.get("hypotheses", []),
        "matched_hypothesis": bench_assessment.get("matched_hypothesis"),
        "candidate_prefixes": bench_assessment.get("candidate_prefixes", []),
        "next_observation": payload.get("next_observation"),
        "decision": payload.get("decision"),
        "decision_scope": payload.get("decision_scope"),
    }


def render_prompt(summary: Mapping[str, Any]) -> str:
    """Build a narration prompt that forbids altering any fixed figure."""

    lines = [
        "You are narrating an already-decided, already-sealed laboratory case file.",
        "The figures below are fixed. Do not alter, contradict, or extend them.",
        "Do not state or imply a diagnosis of the real vehicle.",
        "",
        f"case_id: {summary['case_id']}",
        "mechanic_observations:",
    ]
    lines.extend(f"  - {text}" for text in summary["mechanic_observations"])
    lines.append("hypotheses:")
    for hypothesis in summary["hypotheses"]:
        lines.append(
            f"  - {hypothesis.get('id')} ({hypothesis.get('mechanism')}): "
            f"{hypothesis.get('prediction')}"
        )
    lines.append(f"matched_hypothesis: {summary['matched_hypothesis']}")
    lines.append(f"candidate_prefixes: {list(summary['candidate_prefixes'])}")
    lines.append(f"next_observation: {summary['next_observation']}")
    lines.append(f"decision: {summary['decision']}")
    lines.append(f"decision_scope: {summary['decision_scope']}")
    lines.append("")
    lines.append("Write a short, plain-language explanation of the above for a mechanic.")
    return "\n".join(lines)


def null_narrator(prompt: str) -> str:
    """Deterministic, offline default narrator used in tests and development.

    It does not call any network service. It restates the fixed figures in a
    template sentence so the narration contract can be exercised without a
    real backend.
    """

    lines = prompt.splitlines()
    fields = dict(line.strip().split(": ", 1) for line in lines if ": " in line and not line.strip().startswith("-"))
    case_id = fields.get("case_id", "unknown")
    matched = fields.get("matched_hypothesis", "None")
    next_observation = fields.get("next_observation", "")
    return (
        f"Case {case_id}: the laboratory did not reach a vehicle diagnosis. "
        f"Matched bench hypothesis: {matched}. "
        f"Suggested next observation: {next_observation}"
    )


def narrate(case_file: Mapping[str, Any], narrator: Narrator = null_narrator) -> dict[str, Any]:
    """Produce a case-narrative.v1 artifact beside, never inside, the seal."""

    summary = build_narration_summary(case_file)
    text = narrator(render_prompt(summary))
    if not isinstance(text, str) or not text.strip():
        raise ValueError("narrator must return non-empty text")
    return {
        "schema_version": NARRATION_SCHEMA_VERSION,
        "case_id": summary["case_id"],
        "text": text,
        "backend": getattr(narrator, "__name__", narrator.__class__.__name__),
    }
