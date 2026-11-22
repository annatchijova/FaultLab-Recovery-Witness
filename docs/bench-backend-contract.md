# Portable bench backend contract

This contract is the compatibility boundary between the host investigator and a
native bench backend. A backend selected with `--bench` must implement the
existing positional command-line contract:

```text
BENCH --fault FAULT --case-id CASE --run-id RUN --oracle-file PATH [--interactive]
```

The `--interactive` option adds a newline-delimited request protocol over
standard input and output.

- `NEXT\n` releases exactly one event as one JSON line.
- `CHECK_RESTART\n` and `CHECK_RECOVERY\n` return `YES\n` or `NO\n`
  about the pending event. They do not advance the event cursor.
- After all events, `NEXT\n` returns `END\n` and the process exits zero.
- Any malformed request, incomplete session, serialization failure or oracle
  write failure exits nonzero.
- Standard output contains only protocol responses and public event records.
  Diagnostics belong on standard error.

Each public record has exactly these fields:

| Field | Contract |
|---|---|
| `schema_version` | `event.v1` |
| `case_id`, `run_id` | 1–128 ASCII letters, digits, period, underscore or hyphen |
| `sequence` | positive integer, contiguous from 1 |
| `source` | `bench` |
| `clock_domain` | `simulated` |
| `event_type` | nonempty string |
| `observed` | boolean true |

The batch output is the same ordered event sequence without request handshakes.
The private oracle is written to the supplied path and remains unavailable to
the investigator. Event names and their interpretation must be documented per
backend. A QNX event must not inherit host-fixture meaning by name alone.

Run the backend conformance check against any candidate executable:

```sh
cmake -S . -B build
cmake --build build
python3 tools/check_host_replay.py --bench build/ecu_bench
```

The check exercises batch, interactive and query sessions for each fixture,
checks the public event signatures, verifies sealed cases, and repeats runs
with fixed IDs to compare deterministic bytes. Passing it establishes protocol
compatibility with the current fixtures. It does not establish QNX-specific
persistence, IPC, timing, kernel trace or power interruption semantics.
