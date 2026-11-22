# Security Audit — Recovery Witness host backend
## Red Team Round 3

**Date:** 2026-11-22
**Method:** Abductive Engineering (observe, predict, test) and invariant review
**Scope:** C++ host fixture, Python acquisition boundary, event/case verification, recorder comparison and backend conformance. QNX, external recorder authenticity, and vehicle evidence were unavailable.
**Base:** `main` @ `301cc5c`
**Reproducible checks:** `tests/test_capture_boundaries.py`, `tests/test_case_consumers.py`, `tests/test_direct_evidence.py`, `tests/test_host_sample.py`, `tests/identifiers.cmake`, `tools/check_host_replay.py`

## Threat model

- Attacker can provide CLI values, mechanic observations, malformed or oversized backend output, pre-existing artifact paths, and edited case or sample files.
- Attacker cannot replace trusted source code, Python runtime, executable after selection, or filesystem implementation.
- QNX kernel behavior and independent recorder behavior were not tested.

## Epistemic legend

CODE FACT means directly inspected. CONFIRMED BY INDUCTION means executed against this revision. FALSIFIED means the predicted effect did not occur under tested conditions. No claim below implies hostile control of a trusted executable.

## Executive summary

| ID | Severity | Level | Module | Finding |
|---|---|---|---|---|
| R3-01 | Medium | CODE FACT | CLI artifact publication | Two-file publication is collision-safe and ordered, but interruption can leave an oracle orphan. |
| R3-02 | Medium | CODE FACT | Integrity verifier | Hashes detect edits relative to received bytes; they do not authenticate source or establish a trusted root. |
| R3-03 | Medium | CONFIRMED BY INDUCTION | Host query protocol | Query and returned event are computed from the same fixture; agreement proves protocol consistency only. |
| R3-04 | Low | CODE FACT | Legacy case handling | Historical pre-chain cases can be read, but cannot establish chained event integrity. |

## Findings

### R3-01 — Oracle may remain without its case
**Bucket:** operational limitation. **Level:** CODE FACT.

- **Observation:** CLI stages both artifacts, links the oracle first, and the case last. It removes the oracle if the second link fails during normal execution.
- **Baseline:** The case is the documented completion marker.
- **Abduction:** Process or machine interruption between links prevents rollback code from running.
- **Deduction:** An interrupted attempt can leave an oracle path while no case path exists.
- **Induction:** Not fault-injected in this round. The report caps this at source-confirmed behavior, not reproduction.
- **Disposition:** The custody guide describes orphan handling and requires new paths on retry.

### R3-02 — Integrity is not authentication
**Bucket:** architectural limitation. **Level:** CODE FACT.

- **Observation:** Case and event digests use unkeyed SHA-256.
- **Baseline:** A verifier with no trusted key/checkpoint can recompute internal consistency.
- **Abduction:** A party able to rewrite a whole artifact can recompute its digest.
- **Deduction:** The verifier accepts a structurally valid replacement sealed with a newly computed digest.
- **Induction:** No trusted signature or external checkpoint exists in scope. Cryptographic primitives were not attacked.
- **Disposition:** README and custody guide limit the claim to consistency of received bytes.

### R3-03 — Query answer and event share one source
**Bucket:** evidence-independence limitation. **Level:** CONFIRMED BY INDUCTION.

- **Observation:** Native `CHECK_RESTART` / `CHECK_RECOVERY` inspect the pending fixture event, and the next `NEXT` returns that event.
- **Baseline:** Independent corroboration requires a measurement path not derived from the same fixture state.
- **Abduction:** Matching answer and event may be guaranteed by construction.
- **Deduction:** Each fixture query result should agree with its following event, while this says nothing about a separate recorder.
- **Induction:** `tools/check_host_replay.py --bench build/ecu_bench` exercised all three fixture signatures in batch, interactive, and query modes, with two fixed-ID repetitions. Cases passed the independent verifier and bytes matched within each repeated pair.
- **Disposition:** Backend contract and README scope this as protocol conformance. Recorder independence remains untested.

### R3-04 — Legacy events lack chain guarantees
**Bucket:** compatibility limitation. **Level:** CONFIRMED BY INDUCTION.

- **Observation:** The verifier recognizes the historical projected event schema and marks absent chain status separately.
- **Abduction:** Treating such a case as a current authenticated capture would overstate what it proves.
- **Deduction:** A historical case can remain readable while host replay/comparison requiring current metadata rejects it.
- **Induction:** `tests/test_case_consumers.py` checks a historical projected case retains a valid digest and reports no event-chain status; current capture consumers require full metadata.
- **Disposition:** The review UI labels historical captures without a chain. No legacy case is promoted to a current host capture.

## Discarded vectors

| Vector | Result | Evidence |
|---|---|---|
| Missing, extra, mistyped or malformed public event fields | FALSIFIED as accepted input | Boundary tests reject incomplete keys, unknown fields, non-boolean observations, invalid identifiers and non-integer sequences. |
| Blank interactive line shifts event cursor | FALSIFIED for current parser | Interactive boundary tests reject blank records before cursor advancement. |
| Batch output limit is applied only after buffering | FALSIFIED for current collector | Stream boundary test exceeds stdout and stderr budgets and receives a bounded failure. |
| Existing artifact overwritten on ordinary publication collision | FALSIFIED for tested collision | Capture boundary test confirms a concurrent case remains intact and this attempt's oracle is rolled back. |
| Case with no bench evidence passes as verified host evidence | FALSIFIED | Consumer test reports zero events and `valid=false`. |
| Event hash changes after content mutation | FALSIFIED as undetected in direct API | Direct evidence test mutates a chained event and investigator rejects it. |

## Verification

At the audited revision, clean C++17 configure/build succeeded, CTest passed 2/2, Python tests passed 39/39, and the backend conformance check passed for all three scenarios across batch, interactive and query modes. These checks cover the host fixtures, not QNX semantics.

## Skills applied

`audit-before-patch`, `invariant-hunting`, `red-team-auditing`, and `git-discipline`.
