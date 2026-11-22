"""Independent standard-library verifier for a sealed Recovery Witness case."""

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CANONICALIZE_VERSION = "canonical-json.v1"
GENESIS_HASH = "0" * 64
EVENT_FIELDS = {"case_id", "run_id", "sequence", "source", "schema_version",
                "event_type", "clock_domain", "observed"}
CHAIN_FIELDS = {"prev_hash", "event_hash"}


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


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON field: " + ascii(key))
        obj[key] = value
    return obj


def parse_document(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def verify_document(document):
    """Check the case envelope, observation structure and chain independently."""
    envelope = document if isinstance(document, dict) else {}
    payload = envelope.get("payload")
    envelope_ok = (envelope.get("schema_version") == "sealed-case-file.v1"
                   and envelope.get("canonicalize_version") == CANONICALIZE_VERSION)
    try:
        seal_ok = (envelope_ok and isinstance(payload, dict)
                   and envelope.get("sha256") == _seal(payload))
    except (TypeError, ValueError):
        seal_ok = False
    payload = payload if isinstance(payload, dict) else {}
    schema_ok = (envelope_ok and payload.get("schema_version") == "case-file.v1"
                 and _text(payload.get("case_id")))
    observations = payload.get("observations", [])
    events = []
    if isinstance(observations, list):
        for observation in observations:
            if not isinstance(observation, dict):
                schema_ok = False
            elif observation.get("source") == "bench":
                events.append(observation)
                if not _text(observation.get("event_type")):
                    schema_ok = False
            elif (set(observation) != {"source", "text"} or observation.get("source") != "mechanic"
                  or not _text(observation.get("text"))):
                schema_ok = False
    else:
        schema_ok = False
    chained = any(CHAIN_FIELDS.intersection(event) for event in events)
    # The pre-chain producer projected each event to these three public fields.
    projected = events and all(set(event) == {"source", "sequence", "event_type"} for event in events)
    if projected:
        schema_ok = schema_ok and all(
            type(event["sequence"]) is int and event["sequence"] == position
            for position, event in enumerate(events, 1)
        )
    elif events:
        try:
            host_events(payload, events)
        except ValueError:
            schema_ok = False
    try:
        chain = _verify_events(events) if chained else {"issues": []}
    except (TypeError, ValueError):
        chain = {"linkage_ok": False, "integrity_ok": False,
                 "issues": ["Event contains an unsupported value"]}
    issues = list(chain["issues"])
    if not seal_ok:
        issues.append("Case seal or envelope is invalid")
    if not schema_ok:
        issues.append("Invalid case schema or observations")
    readable = not issues
    if not events:
        issues.append("No host events recorded")
    elif not chained:
        issues.append("Host events have no recorded hash chain")
    return {
        "readable": readable,
        "case_seal_ok": seal_ok,
        "case_schema_ok": schema_ok,
        "bench_event_count": len(events),
        "event_linkage_ok": chain.get("linkage_ok"),
        "event_integrity_ok": chain.get("integrity_ok"),
        "issues": issues,
        "valid": not issues,
    }


def verify(path: Path) -> dict[str, Any]:
    return verify_document(parse_document(path.read_bytes()))


def verified_document(data, *, allow_unattested=False):
    document = parse_document(data)
    result = verify_document(document)
    if not result["valid"] and not (allow_unattested and result["readable"]):
        raise ValueError("Case verification failed: " + ", ".join(result["issues"]))
    return document


def host_events(case, events=None):
    """Require one contiguous, directly observed simulated host capture."""
    if events is None:
        events = [o for o in case.get("observations", []) if o["source"] == "bench"]
    if not events:
        raise ValueError("No host events recorded")
    run_id = events[0].get("run_id")
    for identifier in (case.get("case_id"), run_id):
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", identifier):
            raise ValueError("Invalid host event identifier")
    for position, event in enumerate(events, 1):
        if (set(event) - CHAIN_FIELDS != EVENT_FIELDS or not _text(event["event_type"])
                or event["source"] != "bench" or event.get("run_id") != run_id
                or event.get("case_id") != case.get("case_id")
                or event.get("schema_version") != "event.v1"
                or event.get("clock_domain") != "simulated"
                or event.get("observed") is not True
                or type(event.get("sequence")) is not int or event["sequence"] != position):
            raise ValueError("Invalid host event identity, sequence or observation metadata")
    return events


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} CASE_FILE", file=sys.stderr)
        return 2
    try:
        report = verify(Path(argv[1]))
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as error:
        print(json.dumps({"valid": False, "issues": [str(error)]}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
