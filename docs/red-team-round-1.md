# Red-Team Audit — Host Investigation Vertical Slice

## Round 1

**Date:** 2026-11-18  
**Scope:** C++17 host bench, Python harness, deterministic investigator, case-file sealing, and CLI artifact handling.  
**Out of scope:** OpenAI integration, QNX runtime behavior, real vehicle interfaces, network services, and deployment permissions.  
**Pre-fix base:** cf3a38d  
**Method:** Abductive Engineering with local-boundary and forensic-integrity review.

## Threat model

The attacker or accidental operator may control CLI arguments, mechanic text,
bench output, and paths supplied to the local harness. They may not modify the
repository code, the Python runtime, or the C++ executable after it is built.
The bench oracle is private experimental metadata and must never cross into the
investigator's public evidence boundary.

This is a local-tool threat model. It does not claim protection against a user
who already controls the host, the executable, or the output directory.

## Epistemic legend

- **CODE FACT:** directly observed in the source.
- **PLAUSIBLE HYPOTHESIS:** a code-supported prediction not yet executed.
- **CONFIRMED BY INDUCTION:** the prediction was executed against the live pre-fix implementation.
- **FALSIFIED:** the proposed effect did not occur under the stated conditions.

## Executive summary

| ID | Severity | Level before fix | Area | Finding |
| --- | --- | --- | --- | --- |
| RW-001 | Medium | CONFIRMED BY INDUCTION | CLI artifacts | The case output could overwrite the hidden oracle when both paths matched. |
| RW-002 | Medium | CONFIRMED BY INDUCTION | Event provenance | Every bench run emitted the same case and run identifiers. |
| RW-003 | Medium | CONFIRMED BY INDUCTION | Evidence boundary | Unknown fields and nested hidden-oracle data crossed the parser. |
| RW-004 | Low | CONFIRMED BY INDUCTION | Input contract | Empty mechanic evidence still produced an investigation case. |
| RW-005 | Low | CODE FACT | Native bench JSON | Caller-controlled identifiers were interpolated into JSON without a safe alphabet. |
| RW-006 | Informational | CODE FACT | Chain of custody | Event-level linkage is now present, but complete runs do not yet form an append-only chain. |

The fixes are now present on the working tree and covered by regression tests.

## Findings

### RW-001 — Case output can destroy the hidden oracle

**Bucket:** software vulnerability  
**Severity:** Medium  
**Epistemic level:** Confirmed by induction on cf3a38d.

- **Observation:** The CLI accepted the same path for --oracle-file and --output.
- **Expected context:** The oracle is separate, private experiment metadata.
- **Abduction:** The output writer would atomically replace the oracle after the bench completed.
- **Deduction:** The shared file would end as a sealed case file rather than oracle.v1.
- **Induction:** The pre-fix command completed and the shared file began with a sealed case payload. The oracle artifact was gone.
- **Fix:** validate_artifact_paths rejects path identity before execution.

### RW-002 — Repeated runs are indistinguishable

**Bucket:** forensic-integrity defect  
**Severity:** Medium  
**Epistemic level:** Confirmed by induction on cf3a38d.

- **Observation:** Two independent bench executions emitted case_id=bench-case and run_id=bench-run.
- **Expected context:** Evidence must be joinable to one case and one attempt.
- **Abduction:** Fixed identifiers allow separate runs to be merged or misattributed during replay.
- **Deduction:** The first public event from both runs will have identical identity fields.
- **Induction:** Both runs produced the same identity fields.
- **Fix:** The bench now receives case-id and run-id; identifiers are validated and emitted in public events.

### RW-003 — Public evidence boundary accepted hidden or unknown structure

**Bucket:** software vulnerability  
**Severity:** Medium  
**Epistemic level:** Confirmed by induction on cf3a38d.

- **Observation:** The parser checked hidden keys only at the event top level and preserved unknown fields.
- **Expected context:** The investigator must receive only the public event contract.
- **Abduction:** A nested oracle field or unexpected instruction-bearing field could cross the boundary.
- **Deduction:** Events containing metadata.oracle or unexpected should be rejected.
- **Induction:** Both payloads were accepted by the pre-fix parser.
- **Fix:** Hidden-key detection is recursive, unknown event fields are rejected, and public output is bounded by bytes, line length, event count, and timeout.

### RW-004 — Empty mechanic evidence produced a case

**Bucket:** contract weakness  
**Severity:** Low  
**Epistemic level:** Confirmed by induction on cf3a38d.

- **Observation:** investigate() accepted an empty mechanic-observation tuple and returned ABSTAIN.
- **Expected context:** A mechanic-facing investigation requires at least one real observation.
- **Abduction:** The empty case could create an evidentially vacuous report.
- **Deduction:** Empty input should be rejected at the investigator boundary.
- **Induction:** The pre-fix function returned a case file for empty evidence.
- **Fix:** At least one mechanic observation is required.

### RW-005 — Native event JSON depended on unsafe identifiers

**Bucket:** software vulnerability  
**Severity:** Low  
**Epistemic level:** Code fact before fix; confirmed rejection after fix.

- **Observation:** The C++ bench interpolated identifiers directly into JSON.
- **Expected context:** Identity fields must not break the event serialization contract.
- **Deduction:** A quote in case-id would produce malformed JSON.
- **Induction:** A quote-containing identifier was rejected by the new validator.
- **Fix:** Case and run identifiers must be 1–128 characters from [A-Za-z0-9._-].

### RW-006 — Individual seals are not yet a custody chain

**Bucket:** architectural limitation
**Severity:** Informational
**Epistemic level:** Code fact.

- **Observation:** A case file contains a deterministic SHA-256 seal over its
  payload and public events now carry genesis-linked hashes. Separate runs still
  have no predecessor reference, and the verifier remains in the producer
  package.
- **Expected context:** A per-artifact seal detects modification of that
  artifact. It does not prove that an event was not omitted, reordered, or
  inserted between two independently sealed artifacts.
- **Abduction:** Treating the current seal as a complete chain of custody would
  overstate the evidence guarantee.
- **Deduction:** Reordering or deleting complete event records should now break
  event linkage, while reordering complete runs could remain undetectable.
- **Induction:** The new regression test confirms event reordering breaks
  linkage while preserving the separate integrity result.
- **Disposition:** Event-level linkage is fixed. A future evidence contract
  should chain complete runs, include content hashes for referenced artifacts,
  and move verification into an independent standard-library tool that reports
  linkage and payload integrity separately.

## Discarded or already-refuted vectors

| Vector | Result | Evidence |
| --- | --- | --- |
| Top-level oracle field in a public event | FALSIFIED as a bypass | Existing boundary test rejects fault at the top level. |
| Float entering the sealed decision path | FALSIFIED for current code | Existing sealing test rejects floats. |
| Reordering dictionary keys changes a seal | FALSIFIED for current code | Existing canonicalization test observes equal seals. |
| LLM changes the current verdict | Not applicable to this slice | No OpenAI backend exists yet; the local investigator emits a fixed abstention. |
| QNX timing or IPC claims | Not tested | QNX is outside this host-only round. |
| Backup or restore guarantees | Not applicable | This slice does not create or restore backups. |

## Remediation verification

The following checks were run after the fixes:

~~~text
14 Python unit tests: passed
CTest: 1/1 passed
Host end-to-end CLI: produced sealed-case-file.v1, a 64-character SHA-256 seal,
and a separate oracle artifact
Collision probe: rejected with exit code 1
Unsafe native identifier probe: rejected with exit code 1
~~~

The current implementation is still a research vertical slice. This report
does not establish production security, QNX equivalence, or correctness of a
future model-backed investigator. Event-level chaining is present, but complete
run-level custody and independent verification remain future work.
