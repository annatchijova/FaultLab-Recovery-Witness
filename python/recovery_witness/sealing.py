"""Canonical, typed serialization and SHA-256 sealing for case artifacts."""

import hashlib
import json
from typing import Any


CANONICALIZE_VERSION = "canonical-json.v1"


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
