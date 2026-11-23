"""Render a verified host case as plain text for human review."""

import argparse
import json
from pathlib import Path

from verify_case import verified_document


def quoted(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected non-empty text")
    return json.dumps(value, ensure_ascii=True)


def report(data):
    case = verified_document(data, allow_unattested=True)
    payload = case["payload"]
    lines = ["Case " + quoted(payload["case_id"]), "SHA-256 " + case["sha256"]]
    for source, field in (("mechanic", "text"), ("bench", "event_type")):
        observations = [item for item in payload["observations"] if item["source"] == source]
        lines.append("\n" + source.capitalize() + " observations")
        if not observations:
            lines.append("  No observations recorded")
        elif source == "bench" and "event_hash" not in observations[0]:
            lines.append("  Historical capture without an event hash chain")
        lines.extend("  " + quoted(item[field]) for item in observations)
    if "mechanic_record" in payload:
        record = payload["mechanic_record"]
        lines.append("\nMechanic-reported record (not vehicle ground truth)")
        lines.append("  DTCs: " + (", ".join(record["dtcs"]) if record["dtcs"] else "none reported"))
        if record.get("scanner_report"):
            lines.append("  Scanner report: " + quoted(record["scanner_report"]))
        if record.get("freeze_frame"):
            lines.append("  Freeze frame: " + json.dumps(record["freeze_frame"], sort_keys=True))
        for measurement in record["measurements"]:
            unit = f" {measurement['unit']}" if "unit" in measurement else ""
            lines.append(f"  Measurement: {measurement['name']} = {measurement['value']}{unit}")
        for entry in record["history"]:
            lines.append("  History: " + quoted(entry))
    lines.append("\nCompeting hypotheses")
    if not isinstance(payload["hypotheses"], list) or len(payload["hypotheses"]) < 2:
        raise ValueError("Missing rival hypotheses")
    for item in payload["hypotheses"]:
        lines.append("  " + quoted(item["mechanism"]) + " — " + quoted(item["prediction"]))
    if "bench_assessment" in payload:
        assessment = payload["bench_assessment"]
        lines.append("\nHost experiment\n  " + quoted(assessment["requested_experiment"]))
        lines.append("  " + quoted(assessment["reason"]))
        match = assessment["matched_hypothesis"]
        lines.append("  Matching host hypothesis: " + quoted("unresolved" if match is None else match))
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
