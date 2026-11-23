# Level 1 Mechanic-Facing Case Schema

**Status:** Resolved for Level 1. Closes the "exact Level 1 mechanic-facing
case" open decision in
[`docs/preliminary-levels.md`](preliminary-levels.md).

## Decision

The mechanic-facing case input has two parts, kept structurally separate
because they carry different epistemic weight:

1. **Free-text narrative** (`mechanic_observations`, already existed): the
   mechanic's own account of symptoms. Unstructured, required, at least one
   entry.
2. **Structured mechanic record** (`mechanic_record`, new, optional): DTCs, a
   scanner report, a freeze frame, measurements, and prior test history —
   the inputs Level 1 names in `preliminary-levels.md` (`## Level 1 inputs`).

Both land in the sealed case-file payload as **mechanic-reported, not
vehicle ground truth** — the same rule the project already applies to bench
evidence versus oracle truth. Neither is treated as proof of what happened
in the vehicle; both exist to inform the investigator's view of what to
request next.

## Why a new top-level field instead of extending `observations`

The independently-implemented verifier (`tools/verify_case.py`) enforces a
closed shape for any observation with `source == "mechanic"`: exactly
`{"source", "text"}`. That check is deliberate — it is the thing stopping a
free-form observation from smuggling in extra fields — and it predates this
schema. Rather than loosen it, `mechanic_record` is a separate, additive key
on the case-file payload:

- `verify_case.py` ignores unknown top-level payload keys, so it accepts a
  payload with `mechanic_record` present exactly as it did before (verified
  in `tests/test_investigator.py::test_mechanic_record_is_additive_and_independently_verifiable`,
  which runs the real independent verifier against an enriched payload).
- `tools/review_case.py` renders it in a labeled section
  ("Mechanic-reported record (not vehicle ground truth)") without weakening
  its existing closed-shape checks on `observations`.
- Omitting `mechanic_record` entirely (the default) produces the exact same
  payload as before this change — confirmed by diffing a bare case against
  an enriched one with the key removed.

## Schema: `mechanic-record.v1`

Implemented in `recovery_witness.mechanic_record`:

| Field | Type | Validation |
| --- | --- | --- |
| `dtcs` | list of string | Must match `[PBCU][0-9A-F]{4}` (standard OBD-II form, e.g. `U0100`) |
| `scanner_report` | string or null | Non-empty, bounded length |
| `freeze_frame` | object or null | String keys; no float anywhere, recursively |
| `measurements` | list of `{name, value, unit?}` | `value` is `int` or `str`, never `float`; no extra keys |
| `history` | list of string | Non-empty entries, bounded count |

Floats are rejected at this boundary with a specific `ValueError`, not left
to fail later at `sealing.seal()` with a generic `TypeError` — the same
float-free decision-path invariant the rest of the project already enforces
(`docs/investigator-agent-design.md`, `sealing.py`), just caught closer to
where a mechanic or a CLI caller would actually introduce one.

## CLI

`recovery_witness.cli` accepts `--dtc` (repeatable), `--scanner-report`,
`--freeze-frame JSON`, `--measurement JSON` (repeatable), and
`--mechanic-history` (repeatable). Omitting all of them keeps `main()`
producing exactly the case file it produced before this schema existed.

## What this does not change

- `experiment.assess()` still only sees `bench_observations`. The mechanic
  record does not feed the deterministic hypothesis elimination — it is
  context for the human reviewer and, later, the narrator, not an input to
  the sealed decision.
- The narrator (`docs/investigator-agent-design.md`) is not yet wired to
  read `mechanic_record`; its prompt today only covers hypotheses, the
  bench-matched hypothesis, and the fixed decision. Feeding the structured
  record into the prompt is a natural next step but is left open here.
