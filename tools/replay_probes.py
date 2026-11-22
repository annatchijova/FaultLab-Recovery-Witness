"""Replay adaptive observation requests against one independently verified case."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from recovery_witness.experiment import assess
from verify_case import host_events, verified_document


def replay(path):
    case = verified_document(path.read_bytes())["payload"]
    events = host_events(case)
    visible = 0
    requests = []
    while True:
        result, _ = assess(events[:visible], case["case_id"])
        probe = result["next_bench_probe"]
        if probe is None or probe["sequence"] > len(events):
            break
        visible = probe["sequence"]
        requests.append({**probe, "returned_event": events[visible - 1]["event_type"]})
    full, _ = assess(events, case["case_id"])
    return {"requests": requests, "pending_request": probe,
            "matched_complete_capture": full["matched_hypothesis"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(replay(args.case), indent=2))
    except (ValueError, TypeError, AttributeError, KeyError, OSError) as error:
        parser.exit(1, f"Cannot replay case: {ascii(str(error))}\n")
