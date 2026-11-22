"""Bounded, host-side investigator contract.

This module is deliberately deterministic while the Level 1 contract is being
developed. An OpenAI-backed investigator can be added behind the same boundary;
it must not receive hidden bench-oracle fields or emit a vehicle diagnosis.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .experiment import assess
from .harness import validate_public_event
from .sealing import verify_event_chain


SCHEMA_VERSION = "case-file.v1"
_MAX_CASE_ID_LENGTH = 128
_MAX_TEXT_LENGTH = 2_000
_HIDDEN_KEYS = frozenset({"fault", "injected_fault", "oracle", "oracle_truth"})


def _contains_hidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _HIDDEN_KEYS or _contains_hidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_hidden_key(child) for child in value)
    return False


@dataclass(frozen=True)
class InvestigationInput:
    """Public inputs available to the investigator."""

    case_id: str
    mechanic_observations: tuple[str, ...]
    bench_observations: tuple[Mapping[str, Any], ...]


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > _MAX_TEXT_LENGTH:
        raise ValueError(f"{field} exceeds {_MAX_TEXT_LENGTH} characters")
    return value


def validate_request(case_id: str, mechanic_observations: tuple[str, ...]) -> None:
    case_id = _require_text(case_id, "case_id")
    if len(case_id) > _MAX_CASE_ID_LENGTH:
        raise ValueError(f"case_id exceeds {_MAX_CASE_ID_LENGTH} characters")

    if not isinstance(mechanic_observations, tuple):
        raise ValueError("mechanic_observations must be a tuple")
    if not mechanic_observations:
        raise ValueError("at least one mechanic observation is required")
    for index, observation in enumerate(mechanic_observations):
        _require_text(observation, f"mechanic_observations[{index}]")



def _validate_case(case: InvestigationInput) -> None:
    validate_request(case.case_id, case.mechanic_observations)
    if not isinstance(case.bench_observations, tuple):
        raise ValueError("bench_observations must be a tuple")
    formats = set()
    run_ids = set()
    for index, observation in enumerate(case.bench_observations):
        if not isinstance(observation, Mapping):
            raise ValueError(f"bench_observations[{index}] must be a mapping")
        if _contains_hidden_key(observation):
            raise ValueError(
                f"bench_observations[{index}] contains hidden oracle data"
            )
        if observation.get("source") != "bench":
            raise ValueError(f"bench_observations[{index}] must have source=bench")
        _require_text(observation.get("event_type"), f"bench_observations[{index}].event_type")
        sequence = observation.get("sequence")
        if type(sequence) is not int or sequence != index + 1:
            raise ValueError("Bench observations must have contiguous integer positions")
        if set(observation) == {"source", "event_type", "sequence"}:
            # Historical direct-API observations carry no execution provenance.
            formats.add("legacy")
            continue
        chain_fields = {"prev_hash", "event_hash"} & observation.keys()
        if chain_fields and len(chain_fields) != 2:
            raise ValueError("Incomplete event chain metadata")
        validate_public_event({k: v for k, v in observation.items() if k not in chain_fields})
        if observation["case_id"] != case.case_id:
            raise ValueError("Unexpected observation case identity")
        run_ids.add(observation["run_id"])
        formats.add("chained" if chain_fields else "raw")
    if len(formats) > 1 or len(run_ids) > 1:
        raise ValueError("Mixed observation formats or execution identities")
    if formats == {"chained"}:
        report = verify_event_chain([dict(event) for event in case.bench_observations])
        if not report["linkage_ok"] or not report["integrity_ok"]:
            raise ValueError("Invalid event chain")


def _hypotheses() -> list[dict[str, str]]:
    return [
        {
            "id": "H1",
            "mechanism": "module_power_drop",
            "prediction": "A power interruption should be followed by module initialization evidence.",
        },
        {
            "id": "H2",
            "mechanism": "transport_message_loss",
            "prediction": "Message loss should produce timeouts without module initialization evidence.",
        },
        {
            "id": "H3",
            "mechanism": "incomplete_module_recovery",
            "prediction": "An interrupted persistent transition may leave recovery evidence without a healthy ready state.",
        },
    ]


def investigate(case: InvestigationInput) -> dict[str, Any]:
    """Create a bounded investigation plan from public observations only.

    The result intentionally abstains from diagnosing the vehicle. It describes
    rival mechanisms and one next observation that could discriminate between
    them. The result contains no hidden bench truth.
    """

    _validate_case(case)
    assessment, question = assess(case.bench_observations, case.case_id)
    observations: list[dict[str, Any]] = [
        {"source": "mechanic", "text": text}
        for text in case.mechanic_observations
    ]
    observations.extend(dict(item) for item in case.bench_observations)

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.case_id,
        "observations": observations,
        "hypotheses": _hypotheses(),
        "bench_assessment": assessment,
        "next_observation": question,
        "decision": "ABSTAIN",
        "decision_scope": "The laboratory plan does not establish what happened in the real vehicle.",
    }
