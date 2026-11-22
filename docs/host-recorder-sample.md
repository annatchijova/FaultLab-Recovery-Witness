# Compare an aligned host recorder sample

Run the investigator CLI with `--query`. Supply its sealed case and a separate
recorder JSON file to `python3 tools/compare_host_sample.py CASE SAMPLE`.
The recorder must identify the same host case, run, simulated sequence position
and predicate. Position is one-based. Synchronizing a recorder to that sequence
is the recorder operator's responsibility.

Example synthetic sample:

```json
{"schema_version":"host-recorder-sample.v1","case_id":"demo","run_id":"demo","sequence":3,"clock_domain":"simulated","event_type":"module_restart","recorder":"synthetic-example","observed":null}
```

Use true or false for an explicit measurement of the predicate at that
position. Use null when the recorder could not measure it. Missing records do
not establish absence. The comparison returns AGREES, DISAGREES or UNKNOWN,
references the case seal and hashes the exact sample bytes. An invalid input
exits nonzero. All three valid comparison outcomes exit zero.

Recorder identity and alignment are supplied by the caller. The adapter checks
the declared alignment; the operator must separately establish instrument
calibration and independence. A physical vehicle timestamp cannot be directly
aligned to this simulated sequence domain.
