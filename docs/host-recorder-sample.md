# Compare an aligned host recorder sample

Run the investigator CLI with `--query`. Supply its sealed case and a separate
recorder JSON file to `python3 tools/compare_host_sample.py CASE SAMPLE`.
The recorder must identify the same host case, execution ID, simulated sequence position
and predicate. Position is one-based. Synchronizing a recorder to that sequence
is the recorder operator's responsibility.

For new samples use v2. Copy the run ID from the acquisition and the case
seal from the verified envelope. The following placeholders illustrate their
locations. Substitute the actual values before running the comparison.

Example synthetic sample:

```json
{"schema_version":"host-recorder-sample.v2","case_seal":"<verified case sha256>","case_id":"demo","run_id":"example-attempt-01","sequence":3,"clock_domain":"simulated","event_type":"module_restart","recorder":"synthetic-example","observed":null}
```

Use true or false for an explicit measurement of the predicate at that
position. Use null when the recorder could not measure it. Missing records do
not establish absence. The comparison returns AGREES, DISAGREES or UNKNOWN,
references the case seal and hashes the exact sample bytes. An invalid input
exits nonzero. All three valid comparison outcomes exit zero.

The output reports `sample_binding=case_seal` for v2. Existing v1 records
remain readable with `sample_binding=legacy_declared_coordinates`; those old
records can be ambiguous when execution identifiers are reused.

Recorder identity and alignment are supplied by the caller. The adapter checks
the declared alignment; the operator must separately establish instrument
calibration and independence. A physical vehicle timestamp cannot be directly
aligned to this simulated sequence domain.
