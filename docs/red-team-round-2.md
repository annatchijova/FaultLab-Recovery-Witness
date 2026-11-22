# Host evidence audit, round 2

**Reviewed revision** `5d16e9154a6d957d3e1d4473e266754693a695db`

The review covered the tracked native bench, Python package, tools, tests, CMake configuration, project claims and previous audit dispositions. Independent readers inspected acquisition and evidence consumption. Findings below are source-level findings unless an execution is explicitly named. The test results describe the bundled host fixtures. QNX and external recorders were outside the available environment.

## Findings and closure criteria

| Priority | Finding and consequence | Closure criterion |
|---|---|---|
| High for evidence consumers | In tools/verify_case.py, verify filters observations before checking the chain. Both chain flags start true, including for zero selected events. The aggregate valid flag combines the seal and chain flags without a case-schema check. A non-object payload can also reach payload.get and escape the CLI error handler. Review, replay and comparison each impose a different subset of schema checks. | Distinguish digest validity, schema validity and availability of bench evidence. Explicitly handle supported legacy cases and return structured errors for malformed input. Require each consumer's evidence prerequisites. |
| High for artifact custody | validate_artifact_paths in harness.py compares absolute path strings. Aliases for one directory entry are outside that check. The native oracle writer opens the destination directly, ahead of public acquisition, and checks only that open succeeded. Both harness modes use file existence as the completion check. A previous oracle or a partial artifact can outlive a failed attempt. | Validate destination identity, stage each oracle for the current attempt, check final stream state and define publication/recovery semantics for the oracle and case together. Verify preservation of existing artifacts on failure. |
| Medium | Batch run_bench buffers stdout and stderr before enforcing the stdout byte budget. The parser limit bounds accepted evidence; it does not bound collection memory. Interactive acquisition has a timeout and line budget, but its cursor counts lines while the parser skips blank records. | Enforce limits during collection and advance the interactive cursor only for a validated event. Verify byte, line, count and timeout boundaries in both modes. |
| Medium | Public JSONL rejects unknown keys but does not require all event fields or their intended scalar types. The investigator's direct API has a different contract. assess checks some fields later when deciding a match, after input has already crossed the boundary. | Validate the complete versioned event contract before chaining. Preserve explicit legacy support where required. Distinguish missing evidence from malformed input. |
| Medium | The query CLI passes case_id as run_id. Internal run-binding checks detect disagreement with the requested value but cannot distinguish two attempts with the same case ID. | Separate logical replay identity from execution identity, preserve deterministic replay, and require an unambiguous execution reference for external sample alignment. |
| Medium | compare_host_sample validates sample position strictly, but uses equality for stored event and query positions. It validates the selected event and predicate locally, without validating the complete capture schema. Recorder identity, clock alignment and independence are caller declarations. | Require typed identities and positions on both sides and validate the capture before alignment. Preserve UNKNOWN. Keep recorder provenance claims separate from byte integrity. |
| Medium | The live CHECK commands inspect the pending fixture event. NEXT returns that same fixture event. This establishes protocol consistency. The study also uses fixed scenario order and one template per class. | Keep claims at protocol and fixture level until an independently sourced, aligned observation or held-out dataset exists. |
| Low | The CLI validates mechanic evidence inside investigate after the bench has already run. Failure can leave an oracle for a rejected request. | Validate request-only fields before launching the child process. |
| Architectural | Event hashes and an unkeyed case digest support internal consistency. The verifier has no independently trusted checkpoint, executable identity or predecessor for complete runs. | Explicitly scope verification results; define an external trust anchor if authentication or cross-run custody becomes a requirement. |

## Reassessment of round 1

| Previous finding | Current disposition |
|---|---|
| RW-001, artifact collision | Partial. Literal collision is covered. Destination aliases and failed publication remain open. |
| RW-002, provenance | Partial. Native events carry caller IDs and both acquisition paths check binding. Repeated CLI attempts can share the same IDs. |
| RW-003, hidden fields and limits | Partial. Nested hidden keys and unknown top-level event fields have regression tests. Event typing and acquisition memory limits remain incomplete. |
| RW-004, empty mechanic input | Case rejection retained. Validation still occurs after the bench side effect. |
| RW-005, native identifier encoding | Source inspection confirms length and character filtering before serialization. Native CTest currently exercises help only. Add a durable native regression for identifier acceptance and rejection. |
| RW-006, chain of custody | Independent verifier and per-event linkage are present. Whole-run custody and an authenticated root remain open. The final paragraph of the historical audit predates the independent verifier. |

## Later fixes and verification evidence

- Fresh C++17 configuration and build succeeded; CTest passed 1/1.
- All 25 Python unit tests passed, including requested run binding, incomplete interactive termination, contradictory query replies, altered recorder cases and the unknown sample outcome.
- Batch replay ran all three fixtures twice. The independent verifier accepted all six cases. Each pair matched byte for byte across hash seeds.
- Query mode ran all three fixtures. Each case verified and the saved-case probe replay completed.
- The study completed three development cases and produced human-readable reports. The explicit signature rule matched 3/3, the constant baseline 1/3, and rotated labels 0/3. These are exhaustive fixture counts.
- Source review found matching canonical type ordering and encodings in the producer and verifier. The public investigator keeps the real-vehicle decision at ABSTAIN. No hosted model is in the decision path.

**Skills applied**: audit-before-patch and git-discipline. The review records open work; no product remediation is included in this audit.
