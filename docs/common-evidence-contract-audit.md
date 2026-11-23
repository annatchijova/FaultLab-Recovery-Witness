# Common Evidence Contract — Audit Against `event.v1`

**Status:** Audit only. No schema change made. Addresses the "the common
event and case-file schema" open decision in
[`docs/preliminary-levels.md`](preliminary-levels.md), which names the
required fields in its `## Common evidence contract` section but does not
check the current implementation against them.

## Method

`preliminary-levels.md` lists nine properties every event "should preserve,
at minimum." This audit reads the live schema — `event.v1` as enforced by
`harness.validate_public_event`, `tools/verify_case.py::host_events`, and
`docs/bench-backend-contract.md` — field by field against that list, so the
QNX transition (Level 3, currently blocked on toolchain availability) does
not silently change event meaning later because a gap went unnoticed now.

## Findings

| Required property | Status | Where |
| --- | --- | --- |
| Case, execution identities | **Covered** | `case_id`, `run_id` |
| Operation identity | **Partial** | No field distinct from `run_id` + `sequence`; one run is one operation today, so this is not yet a gap in practice, but nothing stops a future backend from running multiple operations inside one `run_id` |
| Event identity and sequence position | **Partial** | `sequence` gives position; there is no identity independent of position (e.g. no event UUID). `event_hash`, when chained, is a content digest, not an identity assigned at creation |
| Source category | **Narrow** | Only `"bench"` and `"mechanic"` exist. The contract names `vehicle, bench, witness, agent, or oracle` as the category set. Real-vehicle evidence is not distinguished from mechanic narrative by a `source` tag — both currently collapse into `source: "mechanic"` |
| Observation type and epistemic status | **Partial** | `mechanic_record` now carries `epistemic_status` (this session's addition). Bench events carry `observed: true` and `clock_domain: "simulated"`, which imply but do not name an epistemic status. No event carries an explicit `observation_type` |
| Clock domain and timestamp semantics | **Gap** | `clock_domain` exists (`"simulated"`); there is **no timestamp field at all** in `event.v1`. Event order is established only by `sequence`, not by time |
| Correlation references | **Gap** | No field correlates one event to another beyond prefix order and the hash chain. There is no explicit "this event corresponds to that mechanic-reported DTC" link |
| Reference to the original artifact | **Gap** | An event does not record where it came from beyond being inside the case file itself (no path, hash, or identifier of a separate source artifact) |
| Schema and contract version | **Covered** | `schema_version: "event.v1"` on each event; `case-file.v1` / `sealed-case-file.v1` / `mechanic-record.v1` / `case-narrative.v1` on their respective envelopes |
| Integrity metadata | **Covered** | `prev_hash` / `event_hash` when chained; unkeyed SHA-256, scoped per `docs/host-artifact-custody.md` |

## Reading the gaps

The three real gaps — timestamp, correlation, artifact reference — share a
cause: the host fixture is a closed, three-scenario catalogue
(`docs/bench-backend-contract.md`) replayed from a fixed script. Within that
scope, `sequence` already totally orders events, nothing needs correlating
to anything else yet, and the only artifact is the case file itself. The
gaps are invisible today because the system has not yet needed what they
would carry.

They stop being invisible at Level 3. A QNX backend contributes real
runtime timing, IPC, and kernel trace events (`preliminary-levels.md`,
`## Level 3 — QNX bench`) — order alone will not describe concurrent IPC
messages, and an event correlating to a specific trace artifact becomes
load-bearing rather than optional. Adding a timestamp or correlation field
to an already-fixed `event.v1` later is a breaking schema change across the
C++ bench, the Python harness parser, and the independent verifier
simultaneously — exactly the kind of coordinated, versioned change
`versioned-schema-evolution` exists to manage.

## Disposition

This audit intentionally stops at identifying the gap rather than closing
it now, for two reasons:

1. The three real gaps (timestamp, correlation, artifact reference) are
   additive to a schema the host fixtures do not yet need; adding them
   speculatively, before Level 3 defines what a QNX event's timestamp or
   correlation actually needs to mean, risks guessing a shape that has to
   be redone anyway.
2. Any change to `event.v1` here means touching four coordinated places at
   once (`src/ecu_bench.cpp`, `python/recovery_witness/harness.py`,
   `tools/verify_case.py`, and every test asserting the closed field set) —
   a deliberate, reviewed schema bump, not a quiet addition.

The narrow source-category gap (only `bench`/`mechanic`, not the full
`vehicle, bench, witness, agent, oracle` set) is lower-risk to close inside
the existing `mechanic_record` / mechanic-observation boundary without
touching `event.v1` at all, and is a reasonable next step if a future
session wants it: tag mechanic-reported fields that originated from a
device/scanner reading as `vehicle` rather than folding everything into
`mechanic`.

No code changed as part of this audit.
