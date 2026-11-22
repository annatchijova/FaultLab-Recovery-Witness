"""Render a verified host case as plain text for human review."""

import argparse
import json
from pathlib import Path
import tempfile

from verify_case import verify


def quoted(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected non-empty text")
    return json.dumps(value, ensure_ascii=True)


def report(data):
    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory) / "case.json"
        snapshot.write_bytes(data)
        if not verify(snapshot)["valid"]:
            raise ValueError("Case integrity verification failed")
    case = json.loads(data)
    payload = case["payload"]
    if payload["schema_version"] != "case-file.v1":
        raise ValueError("Unsupported investigation schema")
    lines = ["Case " + quoted(payload["case_id"]), "SHA-256 " + case["sha256"]]
    for source, field in (("mechanic", "text"), ("bench", "event_type")):
        observations = [item for item in payload["observations"] if item["source"] == source]
        if not observations:
            raise ValueError("Missing observations from " + source)
        lines.append("\n" + source.capitalize() + " observations")
        lines.extend("  " + quoted(item[field]) for item in observations)
    if any(item["source"] not in ("mechanic", "bench") for item in payload["observations"]):
        raise ValueError("Unknown observation source")
    lines.append("\nCompeting hypotheses")
    if len(payload["hypotheses"]) < 2:
        raise ValueError("Missing rival hypotheses")
    for item in payload["hypotheses"]:
        lines.append("  " + quoted(item["mechanism"]) + " — " + quoted(item["prediction"]))
    if "bench_assessment" in payload:
        assessment = payload["bench_assessment"]
        lines.append("\nHost experiment\n  " + quoted(assessment["requested_experiment"]))
        lines.append("  " + quoted(assessment["reason"]))
        lines.append("  Matching host hypothesis: " + quoted(assessment["matched_hypothesis"] or "unresolved"))
    for label, field in (("Decision", "decision"), ("Scope", "decision_scope"),
                         ("Proposed observation for human review", "next_observation")):
        lines.append("\n" + label + "\n  " + quoted(payload[field]))
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    try:
        print(report(args.case.read_bytes()))
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, f"Cannot render case: {ascii(str(error))}\n")
