"""Acquire a complete host trace over the native NEXT/END protocol."""

import asyncio

from .experiment import assess
from .harness import (
    _BENCH_TIMEOUT_SECONDS, _MAX_EVENT_COUNT, _MAX_EVENT_LINE_LENGTH,
    _MAX_PUBLIC_OUTPUT_BYTES, parse_public_record, staged_oracle, validate_identifier,
)
from .sealing import chain_events


async def _exchange(process, case_id, run_id, query=False):
    events = []
    requests = []
    checks = []
    pending_check = None
    total = 0
    probe = assess(events, case_id)[0]["next_bench_probe"]
    while True:
        if query and len(events) == 2 and probe and probe["sequence"] == 3:
            predictions = probe["predictions"]
            if "module_restart" in predictions.values():
                command, target = "CHECK_RESTART", "module_restart"
            else:
                command, target = "CHECK_RECOVERY", "recovery_started"
            process.stdin.write(command.encode("ascii") + b"\n")
            await process.stdin.drain()
            answer = await process.stdout.readline()
            if answer not in (b"YES\n", b"NO\n"):
                raise ValueError("Invalid observation query answer")
            pending_check = {"sequence": 3, "command": command, "event_type": target,
                             "observed": answer == b"YES\n"}
        process.stdin.write(b"NEXT\n")
        await process.stdin.drain()
        line = await process.stdout.readline()
        if line == b"END\n":
            break
        if not line.endswith(b"\n") or not line.strip():
            raise ValueError("Incomplete interactive bench response")
        total += len(line)
        if total > _MAX_PUBLIC_OUTPUT_BYTES or len(events) >= _MAX_EVENT_COUNT:
            raise ValueError("Interactive capture exceeded its size limit")
        position = len(events) + 1
        event = parse_public_record(line[:-1].decode("utf-8"), position)
        if event["sequence"] != position:
            raise ValueError("Interactive sequence is not contiguous")
        if event["case_id"] != case_id or event["run_id"] != run_id:
            raise ValueError("Unexpected interactive run identity")
        events.append(event)
        if probe and position == probe["sequence"]:
            if pending_check is not None:
                actual = events[-1]["event_type"] == pending_check["event_type"]
                if actual != pending_check["observed"]:
                    raise ValueError("Observation query contradicts the public event")
                checks.append(pending_check)
                pending_check = None
            requests.append({**probe, "returned_event": events[-1]["event_type"]})
            probe = assess(events, case_id)[0]["next_bench_probe"]
    if pending_check is not None:
        raise ValueError("Observation query has no corresponding event")
    process.stdin.close()
    if await process.stdout.read(1) or await process.wait() != 0:
        raise ValueError("Invalid interactive bench completion")
    if not events:
        raise ValueError("bench produced no public events")
    acquisition = {
        "schema_version": "host-acquisition.v1", "protocol": "NEXT/END",
        "requests": requests, "pending_request": probe,
    }
    if query:
        acquisition.update(schema_version="host-acquisition.v2", protocol="query/NEXT/END", checks=checks)
    return tuple(chain_events(list(events))), acquisition


async def acquire(executable, fault, oracle_file, case_id, run_id, query=False):
    validate_identifier(case_id, "case_id")
    validate_identifier(run_id, "run_id")
    with staged_oracle(oracle_file) as pending:
        return await _acquire(executable, fault, pending, case_id, run_id, query)


async def _acquire(executable, fault, oracle_file, case_id, run_id, query):
    process = await asyncio.create_subprocess_exec(
        str(executable), "--fault", fault, "--case-id", case_id, "--run-id", run_id,
        "--oracle-file", str(oracle_file), "--interactive",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=_MAX_EVENT_LINE_LENGTH,
    )
    try:
        return await asyncio.wait_for(_exchange(process, case_id, run_id, query), _BENCH_TIMEOUT_SECONDS)
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.communicate()
