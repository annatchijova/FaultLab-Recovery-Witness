"""Compare a recorder's aligned host sample with a verified simulated query."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from verify_case import verify

TARGETS = {"CHECK_RESTART": "module_restart", "CHECK_RECOVERY": "recovery_started"}


def compare(case_path, sample_path):
    case_bytes = case_path.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory) / "case.json"
        snapshot.write_bytes(case_bytes)
        if not verify(snapshot)["valid"]:
            raise ValueError("Case integrity verification failed")
    envelope = json.loads(case_bytes)
    case = envelope["payload"]
    acquisition = case["acquisition"]
    if acquisition["schema_version"] != "host-acquisition.v2" or acquisition["protocol"] != "query/NEXT/END":
        raise ValueError("Expected a host query capture")
    sample_bytes = sample_path.read_bytes()
    sample = json.loads(sample_bytes)
    if sample["schema_version"] != "host-recorder-sample.v1" or sample["clock_domain"] != "simulated":
        raise ValueError("Unsupported recorder schema or clock domain")
    for field in ("case_id", "run_id", "recorder", "event_type"):
        if not isinstance(sample[field], str) or not sample[field].strip():
            raise ValueError(f"Invalid sample field {field}")
    seq = sample["sequence"]
    measured = sample["observed"]
    if type(seq) is not int or seq < 1 or (measured is not None and type(measured) is not bool):
        raise ValueError("Invalid sample position or observation")
    events = [e for e in case["observations"] if e["source"] == "bench"]
    if seq > len(events) or sample["case_id"] != case["case_id"]:
        raise ValueError("Sample does not align with case")
    event = events[seq - 1]
    if any(event.get(key) != sample[key] for key in ("case_id", "run_id", "clock_domain", "sequence")):
        raise ValueError("Sample does not align with the recorded bench event")
    checks = [q for q in acquisition["checks"] if q["sequence"] == seq and q["event_type"] == sample["event_type"]]
    if len(checks) != 1:
        raise ValueError("Expected one corresponding host query")
    query = checks[0]
    target = TARGETS[query["command"]]
    predicted = query["observed"]
    if (target != sample["event_type"] or type(predicted) is not bool or event.get("observed") is not True
            or predicted != (target == event["event_type"])):
        raise ValueError("Host query is inconsistent with its recorded event")
    status = "UNKNOWN" if measured is None else ("AGREES" if measured == predicted else "DISAGREES")
    return {
        "schema_version": "host-sample-comparison.v1", "comparison": status,
        "case_seal": envelope["sha256"], "sample_sha256": hashlib.sha256(sample_bytes).hexdigest(),
        "case_id": sample["case_id"], "run_id": sample["run_id"], "sequence": seq,
        "recorder": sample["recorder"], "event_type": target, "clock_domain": "simulated",
        "query_observed": predicted, "recorder_observed": measured,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("sample", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(compare(args.case, args.sample), sort_keys=True))
    except (KeyError, OSError, ValueError, IndexError, TypeError, AttributeError) as error:
        parser.exit(1, f"Cannot compare host sample: {ascii(str(error))}\n")
