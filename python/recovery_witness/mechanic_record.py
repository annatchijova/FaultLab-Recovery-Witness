"""Structured mechanic-facing case input for Level 1.

A mechanic reports more than free-text symptoms: diagnostic trouble codes,
a scanner report, a freeze frame, measurements, and prior test history. This
module validates that structured record and turns it into a canonical,
float-free dict suitable for the sealed case-file payload.

This is additive to the existing boundary: `investigator.InvestigationInput`
keeps its free-text `mechanic_observations`, and a `mechanic_record` is a
separate, optional field in the case-file payload (not folded into
`observations`), so the independently-implemented verifier's strict
mechanic-observation shape (`{"source", "text"}`) is unaffected. See
docs/level1-case-schema.md.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "mechanic-record.v1"

_MAX_TEXT_LENGTH = 2_000
_MAX_LIST_LENGTH = 50
_DTC_PATTERN = re.compile(r"^[PBCU][0-9A-F]{4}$")
_MEASUREMENT_KEYS = {"name", "value", "unit"}
_MEASUREMENT_REQUIRED_KEYS = {"name", "value"}


@dataclass(frozen=True)
class MechanicRecord:
    """Public, mechanic-provided structured case input.

    None of these fields are ground truth about the vehicle; they are what
    the mechanic reported, with their own uncertainty. See
    docs/level1-case-schema.md for the provenance rule this encodes.
    """

    dtcs: tuple[str, ...] = ()
    scanner_report: str | None = None
    freeze_frame: Mapping[str, Any] | None = None
    measurements: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    history: tuple[str, ...] = ()


def _require_text(value: Any, field_name: str, *, max_length: int = _MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if len(value) > max_length:
        raise ValueError(f"{field_name} exceeds {max_length} characters")
    return value


def _require_text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    if len(value) > _MAX_LIST_LENGTH:
        raise ValueError(f"{field_name} exceeds {_MAX_LIST_LENGTH} entries")
    for index, item in enumerate(value):
        _require_text(item, f"{field_name}[{index}]")
    return value


def _reject_float(value: Any, field_name: str) -> None:
    """Recursively reject float values and non-string mapping keys.

    Both are rejected again, generically, by sealing.seal() at seal time.
    Checking here too gives a specific error at the mechanic-record
    boundary instead of a generic one once the payload is already being
    sealed.
    """

    if isinstance(value, float):
        raise ValueError(f"{field_name} must not contain a float value")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be strings, got {key!r}")
            _reject_float(child, f"{field_name}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_float(child, f"{field_name}[{index}]")


def _validate_dtcs(dtcs: Any) -> list[str]:
    if not isinstance(dtcs, tuple):
        raise ValueError("dtcs must be a tuple")
    if len(dtcs) > _MAX_LIST_LENGTH:
        raise ValueError(f"dtcs exceeds {_MAX_LIST_LENGTH} entries")
    for index, code in enumerate(dtcs):
        if not isinstance(code, str) or not _DTC_PATTERN.fullmatch(code):
            raise ValueError(
                f"dtcs[{index}] must match a standard OBD-II code (e.g. U0100, P0300)"
            )
    return list(dtcs)


def _validate_freeze_frame(freeze_frame: Any) -> dict[str, Any] | None:
    if freeze_frame is None:
        return None
    if not isinstance(freeze_frame, Mapping):
        raise ValueError("freeze_frame must be a mapping")
    if len(freeze_frame) > _MAX_LIST_LENGTH:
        raise ValueError(f"freeze_frame exceeds {_MAX_LIST_LENGTH} keys")
    for key in freeze_frame:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("freeze_frame keys must be non-empty strings")
    _reject_float(freeze_frame, "freeze_frame")
    return dict(freeze_frame)


def _validate_measurements(measurements: Any) -> list[dict[str, Any]]:
    if not isinstance(measurements, tuple):
        raise ValueError("measurements must be a tuple")
    if len(measurements) > _MAX_LIST_LENGTH:
        raise ValueError(f"measurements exceeds {_MAX_LIST_LENGTH} entries")
    result = []
    for index, item in enumerate(measurements):
        if not isinstance(item, Mapping):
            raise ValueError(f"measurements[{index}] must be a mapping")
        keys = set(item)
        if not keys.issubset(_MEASUREMENT_KEYS) or not _MEASUREMENT_REQUIRED_KEYS.issubset(keys):
            raise ValueError(
                f"measurements[{index}] must have 'name', 'value', and optionally 'unit'"
            )
        _require_text(item["name"], f"measurements[{index}].name")
        value = item["value"]
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError(f"measurements[{index}].value must be an int or a string")
        if isinstance(value, str):
            _require_text(value, f"measurements[{index}].value")
        if "unit" in item:
            _require_text(item["unit"], f"measurements[{index}].unit")
        result.append(dict(item))
    return result


def validate_mechanic_record(record: MechanicRecord) -> dict[str, Any]:
    """Validate a MechanicRecord and return its canonical sealed-payload form."""

    if not isinstance(record, MechanicRecord):
        raise ValueError("mechanic_record must be a MechanicRecord")

    canonical: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": "mechanic",
        "epistemic_status": "reported_by_mechanic_not_verified",
        "dtcs": _validate_dtcs(record.dtcs),
        "measurements": _validate_measurements(record.measurements),
        "history": list(_require_text_tuple(record.history, "history")),
    }
    canonical["scanner_report"] = (
        _require_text(record.scanner_report, "scanner_report")
        if record.scanner_report is not None
        else None
    )
    canonical["freeze_frame"] = _validate_freeze_frame(record.freeze_frame)
    return canonical
