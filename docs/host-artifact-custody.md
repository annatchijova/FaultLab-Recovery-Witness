# Host capture identity and artifact custody

The investigation CLI issues a fresh execution ID for each invocation. Its
JSON result includes that ID. The case ID groups attempts. An operator can
supply `--run-id` to reproduce a logical capture exactly. Reusing an ID is
appropriate for deterministic replay; use a fresh ID for independently
acquired samples. The study assigns distinct execution IDs across invocations
and retains stable report filenames within each study directory.

## Completion and recovery

Give the CLI two new paths. Each artifact is staged on the filesystem of its
destination. The CLI publishes the oracle first and the sealed case last using
exclusive hard links. The appearance of the public case is the completion
marker. If another invocation has claimed either destination, the CLI fails
without replacing the existing artifact. The destination filesystems must
support hard links. Direct use of the native executable does not implement
this two-file publication protocol.

A process interruption between publications can leave an oracle without a
case. Preserve it for inspection and retry with a fresh execution ID and new
paths. Do not attach it to a different case. Publication across two paths does
not provide a power-loss transaction, storage authentication or a cross-run
custody ledger. Access controls for the oracle directory are the operator's
responsibility.

## What the evidence supports

Use the standalone verifier to check internal consistency. Its report
distinguishes the case digest, case schema, count of bench observations and
event-chain checks. Older or incomplete cases can retain a checkable digest
while lacking evidence needed for a host replay or sample comparison.
An unkeyed digest cannot authenticate the recorder, executable or author.
Authentication would require an independently trusted key or checkpoint.

The native query and the event subsequently released by the bench originate
from one fixture. Their agreement checks the acquisition protocol. Recorder
independence, calibration and clock alignment require evidence from outside
the fixture. The three development scenarios supply no held-out vehicle
measurements.
