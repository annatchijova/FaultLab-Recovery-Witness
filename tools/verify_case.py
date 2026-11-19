"""Independent standard-library verifier for a sealed Recovery Witness case."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


CANONICALIZE_VERSION = "canonical-json.v1"
GENESIS_HASH = "0" * 64


def _typed(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        raise TypeError("float is not allowed in a sealed case")
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, list):
        return {"type": "list", "value": [_typed(item) for item in value]}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("case dictionary keys must be strings")
        return {
            "type": "dict",
            "value": {key: _typed(value[key]) for key in sorted(value)},
        }
    raise TypeError(f"unsupported case value: {type(value).__name__}")


def _seal(payload: dict[str, Any]) -> str:
    canonical = {
        "canonicalize_version": CANONICALIZE_VERSION,
        "payload": _typed(payload),
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_hash(event: dict[str, Any], previous_hash: Any) -> str:
    return _seal({"event": event, "prev_hash": previous_hash})


def _verify_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    linkage_ok = True
    integrity_ok = True
    issues: list[str] = []
    previous_hash = GENESIS_HASH
    for index, event in enumerate(events):
        stored_previous = event.get("prev_hash")
        stored_digest = event.get("event_hash")
        if stored_previous != previous_hash:
            linkage_ok = False
            issues.append(f"event {index} has invalid prev_hash")
        content = {
            key: value
            for key, value in event.items()
            if key not in {"prev_hash", "event_hash"}
        }
        if stored_digest != _event_hash(content, stored_previous):
            integrity_ok = False
            issues.append(f"event {index} has invalid event_hash")
        previous_hash = stored_digest if isinstance(stored_digest, str) else ""
    return {
        "linkage_ok": linkage_ok,
        "integrity_ok": integrity_ok,
        "issues": issues,
    }


def verify(path: Path) -> dict[str, Any]:
    case_file = json.loads(path.read_text(encoding="utf-8"))
    payload = case_file["payload"]
    seal_ok = (
        case_file.get("schema_version") == "sealed-case-file.v1"
        and case_file.get("canonicalize_version") == CANONICALIZE_VERSION
        and isinstance(payload, dict)
        and case_file.get("sha256") == _seal(payload)
    )
    events = [
        observation
        for observation in payload.get("observations", [])
        if isinstance(observation, dict) and observation.get("source") == "bench"
    ]
    event_report = _verify_events(events)
    return {
        "case_seal_ok": seal_ok,
        "event_linkage_ok": event_report["linkage_ok"],
        "event_integrity_ok": event_report["integrity_ok"],
        "issues": event_report["issues"],
        "valid": seal_ok
        and event_report["linkage_ok"]
        and event_report["integrity_ok"],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} CASE_FILE", file=sys.stderr)
        return 2
    try:
        report = verify(Path(argv[1]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"valid": False, "issues": [str(error)]}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
