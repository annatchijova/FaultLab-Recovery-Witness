"""Produce three controlled host cases, human reports and a development evaluation."""

import argparse
import json
import sys
import tempfile
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from recovery_witness.harness import build_case_file, run_bench, write_case_file
from recovery_witness.investigator import InvestigationInput, investigate, validate_request
from review_case import report

# Development oracle outcomes are evaluated only after the case has been sealed.
LABELS = {
    "module_restarted": "H1",
    "transport_timeout_without_restart": "H2",
    "module_not_ready_after_recovery": "H3",
}


def run(args, stage):
    validate_request(args.case_id, tuple(args.mechanic_observation))
    attempt = uuid4().hex
    (stage / "private").mkdir()
    expected = []
    predictions = []
    for index, scenario in enumerate(("power_drop", "message_loss", "recovery_incomplete"), 1):
        stem = f"run-{index}"
        run_id = f"{attempt}-{index}"
        oracle = stage / "private" / f"{stem}.json"
        events = run_bench(args.bench.resolve(), scenario, oracle, case_id=args.case_id, run_id=run_id)
        payload = investigate(InvestigationInput(args.case_id, tuple(args.mechanic_observation), events))
        case_path = stage / f"{stem}.json"
        write_case_file(case_path, build_case_file(payload))
        (stage / f"{stem}.txt").write_text(report(case_path.read_bytes()) + "\n", encoding="utf-8")
        predictions.append(payload["bench_assessment"]["matched_hypothesis"])
        truth = json.loads(oracle.read_bytes())
        if truth["schema_version"] != "oracle.v1" or truth["fault"] != scenario:
            raise ValueError("Unexpected development oracle")
        expected.append(LABELS[truth["outcome"]])

    correct = sum(a == b for a, b in zip(predictions, expected))
    rotated = expected[1:] + expected[:1]
    evaluation = {
        "schema_version": "host-fixture-evaluation.v1",
        "cases": len(expected),
        "rule_correct": correct,
        "constant_baseline_correct": max(expected.count(label) for label in expected),
        "rotated_label_control_correct": sum(a == b for a, b in zip(predictions, rotated)),
        "outcomes": [{"run": i, "expected": y, "predicted": p}
                     for i, (y, p) in enumerate(zip(expected, predictions), 1)],
        "ml_disposition": "Deferred: each mechanism has one independent fixture; no within-class holdout exists.",
        "scope": "Exhaustive development fixture comparison. Population accuracy is unknown.",
    }
    write_case_file(stage / "private/evaluation.json", evaluation)
    return correct == len(expected) and evaluation["rotated_label_control_correct"] == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--mechanic-observation", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True, help="New study directory")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.mkdir()
    try:
        with tempfile.TemporaryDirectory(dir=args.output) as temporary:
            stage = Path(temporary) / "study"
            stage.mkdir()
            passed = run(args, stage)
            stage.rename(args.output / "study")
    except BaseException:
        args.output.rmdir()
        raise
    print(args.output / "study/private/evaluation.json")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
