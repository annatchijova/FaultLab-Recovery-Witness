"""Canonical, typed serialization and SHA-256 sealing for case artifacts."""

import hashlib
import json
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
        raise TypeError("float is not allowed in the sealed decision path")
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, list):
        return {"type": "list", "value": [_typed(item) for item in value]}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("sealed payload dictionary keys must be strings")
        return {
            "type": "dict",
            "value": {
                key: _typed(value[key])
                for key in sorted(value)
            },
        }
    raise TypeError(f"unsupported value in sealed path: {type(value).__name__}")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Return deterministic bytes for a typed, recursively sorted payload."""

    if not isinstance(payload, dict):
        raise TypeError("sealed payload must be a dictionary")
    canonical = {
        "canonicalize_version": CANONICALIZE_VERSION,
        "payload": _typed(payload),
    }
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def seal(payload: dict[str, Any]) -> str:
    """Return a SHA-256 digest over the canonical payload bytes."""

    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _event_digest(event: dict[str, Any], previous_hash: str) -> str:
    return seal({"event": event, "prev_hash": previous_hash})


def chain_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a genesis-linked, deterministic hash chain to public events."""

    chained: list[dict[str, Any]] = []
    previous_hash = GENESIS_HASH
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("event chain entries must be dictionaries")
        chained_event = dict(event)
        chained_event["prev_hash"] = previous_hash
        chained_event["event_hash"] = _event_digest(event, previous_hash)
        chained.append(chained_event)
        previous_hash = chained_event["event_hash"]
    return chained


def verify_event_chain(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Independently report linkage and payload integrity for an event chain."""

    linkage_ok = True
    integrity_ok = True
    issues: list[str] = []
    previous_hash = GENESIS_HASH
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            integrity_ok = False
            issues.append(f"entry {index} is not an object")
            continue
        stored_previous = event.get("prev_hash")
        stored_digest = event.get("event_hash")
        if stored_previous != previous_hash:
            linkage_ok = False
            issues.append(f"entry {index} has an invalid prev_hash")
        content = {
            key: value
            for key, value in event.items()
            if key not in {"prev_hash", "event_hash"}
        }
        if stored_digest != _event_digest(content, stored_previous):
            integrity_ok = False
            issues.append(f"entry {index} has an invalid event_hash")
        if isinstance(stored_digest, str):
            previous_hash = stored_digest
        else:
            previous_hash = ""
    return {
        "linkage_ok": linkage_ok,
        "integrity_ok": integrity_ok,
        "issues": issues,
    }
