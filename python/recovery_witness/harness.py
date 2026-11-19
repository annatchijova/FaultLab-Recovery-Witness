"""Host harness boundary between the C++ bench and the Python investigator."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .sealing import CANONICALIZE_VERSION, chain_events, seal


_HIDDEN_KEYS = frozenset({"fault", "injected_fault", "oracle", "oracle_truth"})
_PUBLIC_EVENT_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "run_id",
        "sequence",
        "source",
        "clock_domain",
        "event_type",
        "observed",
    }
)
_MAX_PUBLIC_OUTPUT_BYTES = 1_000_000
_MAX_EVENT_LINE_LENGTH = 16_384
_MAX_EVENT_COUNT = 1_024
_BENCH_TIMEOUT_SECONDS = 5


def _contains_hidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _HIDDEN_KEYS or _contains_hidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_hidden_key(child) for child in value)
    return False


def parse_public_events(lines: str) -> tuple[dict[str, Any], ...]:
    """Parse public JSONL events while rejecting hidden oracle material."""

    if len(lines.encode("utf-8")) > _MAX_PUBLIC_OUTPUT_BYTES:
        raise ValueError("bench public output exceeds size limit")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines.splitlines(), start=1):
        if not line.strip():
            continue
        if len(line.encode("utf-8")) > _MAX_EVENT_LINE_LENGTH:
            raise ValueError(f"event on line {line_number} exceeds size limit")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid event JSON on line {line_number}") from error
        if not isinstance(event, dict):
            raise ValueError(f"event on line {line_number} must be an object")
        if _contains_hidden_key(event):
            raise ValueError(f"event on line {line_number} contains hidden oracle data")
        if set(event) - _PUBLIC_EVENT_KEYS:
            raise ValueError(f"event on line {line_number} contains unknown fields")
        if event.get("schema_version") != "event.v1":
            raise ValueError(f"event on line {line_number} has an unsupported schema")
        if event.get("source") != "bench":
            raise ValueError(f"event on line {line_number} must have source=bench")
        if not isinstance(event.get("event_type"), str) or not event["event_type"]:
            raise ValueError(f"event on line {line_number} has no event_type")
        sequence = event.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError(f"event on line {line_number} has an invalid sequence")
        events.append(event)
        if len(events) > _MAX_EVENT_COUNT:
            raise ValueError("bench produced too many public events")
    if not events:
        raise ValueError("bench produced no public events")
    sequences = [event["sequence"] for event in events]
    if sequences != list(range(1, len(sequences) + 1)):
        raise ValueError("public event sequence is not contiguous")
    return tuple(events)


def run_bench(
    executable: Path,
    fault: str,
    oracle_file: Path,
    *,
    case_id: str = "bench-case",
    run_id: str = "bench-run",
) -> tuple[dict[str, Any], ...]:
    """Run the bench and return public events without reading the oracle."""

    try:
        completed = subprocess.run(
            [
                str(executable),
                "--fault",
                fault,
                "--case-id",
                case_id,
                "--run-id",
                run_id,
                "--oracle-file",
                str(oracle_file),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=_BENCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("bench exceeded its execution timeout") from error
    if len(completed.stdout.encode("utf-8")) > _MAX_PUBLIC_OUTPUT_BYTES:
        raise RuntimeError("bench public output exceeds size limit")
    if completed.returncode != 0:
        raise RuntimeError(
            f"bench failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    if not oracle_file.is_file():
        raise RuntimeError("bench did not create its separate oracle artifact")
    return tuple(chain_events(list(parse_public_events(completed.stdout))))


def build_case_file(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Wrap an investigation payload in a deterministic sealed envelope."""

    if not isinstance(payload, dict):
        payload = dict(payload)
    if payload.get("schema_version") != "case-file.v1":
        raise ValueError("case payload must use schema_version=case-file.v1")
    if _contains_hidden_key(payload):
        raise ValueError("case payload contains hidden oracle data")
    return {
        "schema_version": "sealed-case-file.v1",
        "canonicalize_version": CANONICALIZE_VERSION,
        "payload": payload,
        "sha256": seal(payload),
    }


def verify_case_file(case_file: Mapping[str, Any]) -> bool:
    """Verify the envelope and digest without trusting narrative fields."""

    if not isinstance(case_file, Mapping):
        raise ValueError("case file must be an object")
    if case_file.get("schema_version") != "sealed-case-file.v1":
        raise ValueError("unsupported case file schema")
    if case_file.get("canonicalize_version") != CANONICALIZE_VERSION:
        raise ValueError("unsupported canonicalization version")
    payload = case_file.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("case file payload must be an object")
    expected = case_file.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("case file has an invalid seal")
    return expected == seal(dict(payload))


def validate_artifact_paths(*, path: Path, oracle_file: Path) -> None:
    """Reject an output path that would destroy the hidden oracle artifact."""

    if path.absolute() == oracle_file.absolute():
        raise ValueError("case output and oracle file must be different paths")


def write_case_file(path: Path, case_file: Mapping[str, Any]) -> None:
    """Write a case file atomically within its destination directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            json.dump(case_file, temporary, ensure_ascii=False, sort_keys=True, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)
