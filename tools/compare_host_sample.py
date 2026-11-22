"""Compare a recorder's aligned host sample with a verified simulated query."""

import argparse
import hashlib
import json
from pathlib import Path

from verify_case import host_events, parse_document, verified_document

TARGETS = {"CHECK_RESTART": "module_restart", "CHECK_RECOVERY": "recovery_started"}


def compare(case_path, sample_path):
    envelope = verified_document(case_path.read_bytes())
    case = envelope["payload"]
    acquisition = case["acquisition"]
    if acquisition["schema_version"] != "host-acquisition.v2" or acquisition["protocol"] != "query/NEXT/END":
        raise ValueError("Expected a host query capture")
    sample_bytes = sample_path.read_bytes()
    sample = parse_document(sample_bytes)
    version = sample["schema_version"]
    if version not in ("host-recorder-sample.v1", "host-recorder-sample.v2") or sample["clock_domain"] != "simulated":
        raise ValueError("Unsupported recorder schema or clock domain")
    bound = version == "host-recorder-sample.v2"
    if (bound or "case_seal" in sample) and sample.get("case_seal") != envelope["sha256"]:
        raise ValueError("Sample case seal differs from the verified case")
    for field in ("case_id", "run_id", "recorder", "event_type"):
        if not isinstance(sample[field], str) or not sample[field].strip():
            raise ValueError(f"Invalid sample field {field}")
    seq = sample["sequence"]
    measured = sample["observed"]
    if type(seq) is not int or seq < 1 or (measured is not None and type(measured) is not bool):
        raise ValueError("Invalid sample position or observation")
    events = host_events(case)
    if seq > len(events) or sample["case_id"] != case["case_id"]:
        raise ValueError("Sample does not align with case")
    event = events[seq - 1]
    if any(event.get(key) != sample[key] for key in ("case_id", "run_id", "clock_domain", "sequence")):
        raise ValueError("Sample does not align with the recorded bench event")
    checks = acquisition["checks"]
    if not isinstance(checks, list):
        raise ValueError("Expected a list of host observation queries")
    predictions = {}
    for query in checks:
        if not isinstance(query, dict) or set(query) != {"command", "event_type", "observed", "sequence"}:
            raise ValueError("Invalid host observation query")
        position = query["sequence"]
        target = query["event_type"]
        prediction = query["observed"]
        if (type(position) is not int or not 1 <= position <= len(events)
                or query["command"] not in TARGETS or TARGETS[query["command"]] != target
                or type(prediction) is not bool or prediction != (events[position - 1]["event_type"] == target)
                or (position, target) in predictions):
            raise ValueError("Host query is inconsistent with its recorded event")
        predictions[position, target] = prediction
    target = sample["event_type"]
    if (seq, target) not in predictions:
        raise ValueError("Missing corresponding host query")
    predicted = predictions[seq, target]
    status = "UNKNOWN" if measured is None else ("AGREES" if measured == predicted else "DISAGREES")
    return {
        "schema_version": "host-sample-comparison.v1", "comparison": status,
        "sample_binding": "case_seal" if bound else "legacy_declared_coordinates",
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
