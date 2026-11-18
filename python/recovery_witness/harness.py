"""Host harness boundary between the C++ bench and the Python investigator."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .sealing import CANONICALIZE_VERSION, seal


_HIDDEN_KEYS = frozenset({"fault", "injected_fault", "oracle", "oracle_truth"})


def parse_public_events(lines: str) -> tuple[dict[str, Any], ...]:
    """Parse public JSONL events while rejecting hidden oracle material."""

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid event JSON on line {line_number}") from error
        if not isinstance(event, dict):
            raise ValueError(f"event on line {line_number} must be an object")
        if _HIDDEN_KEYS.intersection(event):
            raise ValueError(f"event on line {line_number} contains hidden oracle data")
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
) -> tuple[dict[str, Any], ...]:
    """Run the bench and return public events without reading the oracle."""

    completed = subprocess.run(
        [str(executable), "--fault", fault, "--oracle-file", str(oracle_file)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"bench failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    if not oracle_file.is_file():
        raise RuntimeError("bench did not create its separate oracle artifact")
    return parse_public_events(completed.stdout)


def build_case_file(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Wrap an investigation payload in a deterministic sealed envelope."""

    if not isinstance(payload, dict):
        payload = dict(payload)
    if payload.get("schema_version") != "case-file.v1":
        raise ValueError("case payload must use schema_version=case-file.v1")
    return {
        "schema_version": "sealed-case-file.v1",
        "canonicalize_version": CANONICALIZE_VERSION,
        "payload": payload,
        "sha256": seal(payload),
    }


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
