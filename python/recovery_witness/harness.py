"""Host harness boundary between the C++ bench and the Python investigator."""

import asyncio
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import stat
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


def validate_identifier(value: Any, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value):
        raise ValueError(f"invalid {field}: expected 1..128 identifier characters")


def validate_public_event(event: Any) -> None:
    """Validate one raw event.v1 record before attaching chain metadata."""
    if not isinstance(event, dict) or set(event) != _PUBLIC_EVENT_KEYS:
        raise ValueError("public event must contain exactly the event.v1 fields")
    if event["schema_version"] != "event.v1" or event["source"] != "bench":
        raise ValueError("unsupported public event schema or source")
    if event["clock_domain"] != "simulated" or event["observed"] is not True:
        raise ValueError("invalid public event clock domain or observation flag")
    for key in ("case_id", "run_id"):
        validate_identifier(event[key], key)
    if not isinstance(event["event_type"], str) or not event["event_type"].strip():
        raise ValueError("public event has no event_type")
    if type(event["sequence"]) is not int or event["sequence"] < 1:
        raise ValueError("public event has an invalid sequence")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def parse_public_record(line: str, position: int) -> dict[str, Any]:
    if len(line.encode("utf-8")) > _MAX_EVENT_LINE_LENGTH:
        raise ValueError(f"event on line {position} exceeds size limit")
    try:
        event = json.loads(line, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid event JSON on line {position}") from error
    validate_public_event(event)
    return event


def parse_public_events(lines: str) -> tuple[dict[str, Any], ...]:
    """Parse public JSONL events while rejecting hidden oracle material."""

    if len(lines.encode("utf-8")) > _MAX_PUBLIC_OUTPUT_BYTES:
        raise ValueError("bench public output exceeds size limit")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines.split("\n"), start=1):
        if not line.strip():
            continue
        events.append(parse_public_record(line, line_number))
        if len(events) > _MAX_EVENT_COUNT:
            raise ValueError("bench produced too many public events")
    if not events:
        raise ValueError("bench produced no public events")
    sequences = [event["sequence"] for event in events]
    if sequences != list(range(1, len(sequences) + 1)):
        raise ValueError("public event sequence is not contiguous")
    return tuple(events)


@contextmanager
def staged_oracle(destination: Path):
    """Publish only the regular, nonempty oracle produced by this invocation."""
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        pending = Path(directory) / "oracle.json"
        yield pending
        try:
            metadata = pending.lstat()
        except FileNotFoundError as error:
            raise RuntimeError("bench did not create its separate oracle artifact") from error
        if not stat.S_ISREG(metadata.st_mode) or not metadata.st_size:
            raise RuntimeError("bench oracle artifact is empty or not a regular file")
        os.replace(pending, destination)


async def _bounded_batch(arguments):
    process = await asyncio.create_subprocess_exec(
        *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    async def read_stream(stream, limit):
        output = bytearray()
        while chunk := await stream.read(8192):
            if len(output) + len(chunk) > limit:
                raise RuntimeError("bench output exceeds size limit")
            output.extend(chunk)
        return output

    readers = [
        asyncio.create_task(read_stream(process.stdout, _MAX_PUBLIC_OUTPUT_BYTES)),
        asyncio.create_task(read_stream(process.stderr, _MAX_EVENT_LINE_LENGTH)),
    ]

    async def collect():
        output, errors = await asyncio.gather(*readers)
        status = await process.wait()
        if status:
            raise RuntimeError(f"bench failed with exit code {status}: {errors.decode('utf-8', 'replace').strip()}")
        return output.decode("utf-8")

    try:
        return await asyncio.wait_for(collect(), _BENCH_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as error:
        raise RuntimeError("bench exceeded its execution timeout") from error
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        # Consume buffered bytes so pipe shutdown can complete after a limit error.
        await process.communicate()


def _collect_batch(arguments):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_bounded_batch(arguments))
    with ThreadPoolExecutor(max_workers=1) as worker:
        return worker.submit(asyncio.run, _bounded_batch(arguments)).result()


def run_bench(
    executable: Path,
    fault: str,
    oracle_file: Path,
    *,
    case_id: str = "bench-case",
    run_id: str = "bench-run",
) -> tuple[dict[str, Any], ...]:
    """Run the bench and return public events without reading the oracle."""

    validate_identifier(case_id, "case_id")
    validate_identifier(run_id, "run_id")
    with staged_oracle(oracle_file) as pending:
        lines = _collect_batch([
            str(executable), "--fault", fault, "--case-id", case_id,
            "--run-id", run_id, "--oracle-file", str(pending),
        ])
        events = parse_public_events(lines)
        if any(event["case_id"] != case_id or event["run_id"] != run_id for event in events):
            raise ValueError("Public event identity differs from the requested bench run")
        return tuple(chain_events(list(events)))


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

    if (path.resolve() == oracle_file.resolve() or
            (path.exists() and oracle_file.exists() and path.samefile(oracle_file))):
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
