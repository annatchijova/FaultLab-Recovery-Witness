"""Acquire a complete host trace over the native NEXT/END protocol."""

import asyncio

from .experiment import assess
from .harness import (
    _BENCH_TIMEOUT_SECONDS, _MAX_EVENT_COUNT, _MAX_EVENT_LINE_LENGTH,
    _MAX_PUBLIC_OUTPUT_BYTES, parse_public_events,
)
from .sealing import chain_events


async def _exchange(process, case_id, run_id):
    lines = []
    requests = []
    events = ()
    total = 0
    probe = assess(events, case_id)[0]["next_bench_probe"]
    while True:
        process.stdin.write(b"NEXT\n")
        await process.stdin.drain()
        line = await process.stdout.readline()
        if line == b"END\n":
            break
        if not line.endswith(b"\n"):
            raise ValueError("Incomplete interactive bench response")
        total += len(line)
        if total > _MAX_PUBLIC_OUTPUT_BYTES or len(lines) >= _MAX_EVENT_COUNT:
            raise ValueError("Interactive capture exceeded its size limit")
        lines.append(line.decode("utf-8"))
        if probe and len(lines) == probe["sequence"]:
            events = parse_public_events("".join(lines))
            if any(event.get("case_id") != case_id or event.get("run_id") != run_id for event in events):
                raise ValueError("Unexpected interactive run identity")
            requests.append({**probe, "returned_event": events[-1]["event_type"]})
            probe = assess(events, case_id)[0]["next_bench_probe"]
    process.stdin.close()
    if await process.stdout.read(1) or await process.wait() != 0:
        raise ValueError("Invalid interactive bench completion")
    events = parse_public_events("".join(lines))
    if any(event.get("case_id") != case_id or event.get("run_id") != run_id for event in events):
        raise ValueError("Unexpected interactive run identity")
    return tuple(chain_events(list(events))), {
        "schema_version": "host-acquisition.v1", "protocol": "NEXT/END",
        "requests": requests, "pending_request": probe,
    }


async def acquire(executable, fault, oracle_file, case_id, run_id):
    process = await asyncio.create_subprocess_exec(
        str(executable), "--fault", fault, "--case-id", case_id, "--run-id", run_id,
        "--oracle-file", str(oracle_file), "--interactive",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=_MAX_EVENT_LINE_LENGTH,
    )
    try:
        result = await asyncio.wait_for(_exchange(process, case_id, run_id), _BENCH_TIMEOUT_SECONDS)
        if not oracle_file.is_file():
            raise ValueError("Missing separate bench oracle")
        return result
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.communicate()
